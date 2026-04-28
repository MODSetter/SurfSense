"""
DoomLoopMiddleware — pattern-based detector for repeated identical tool calls.

Mirrors ``opencode/packages/opencode/src/session/processor.ts`` doom-loop
behavior. When the same tool with the same arguments is called N times
in a row, the agent has likely entered an infinite loop. We surface this
to the user as an interrupt with ``permission="doom_loop"`` so the UI
can render an "Are you stuck? Continue / cancel?" affordance.

Tier 1.11 in the OpenCode-port plan.

This ships **OFF by default** until the frontend explicitly handles
``context.permission == "doom_loop"`` interrupts (the plan flips
``SURFSENSE_ENABLE_DOOM_LOOP=true`` once the UI is ready).

Wire format: uses SurfSense's existing ``interrupt()`` payload shape
(see ``app/agents/new_chat/tools/hitl.py``):

    {
        "type": "permission_ask",
        "action": {"tool": <name>, "params": <args>},
        "context": {"permission": "doom_loop", "recent_signatures": [...]},
    }

so the frontend that already handles HITL prompts can render this with
no changes beyond a string check.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import deque
from typing import Any

from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
    ContextT,
    ResponseT,
)
from langchain_core.messages import AIMessage
from langgraph.config import get_config
from langgraph.runtime import Runtime
from langgraph.types import interrupt

from app.observability import otel as ot

logger = logging.getLogger(__name__)


def _signature(name: str, args: Any) -> str:
    """Hash a tool call ``(name, args)`` to a short signature."""
    try:
        canonical = json.dumps(args, sort_keys=True, default=str)
    except (TypeError, ValueError):
        canonical = repr(args)
    digest = hashlib.sha1(f"{name}::{canonical}".encode()).hexdigest()
    return digest[:16]


class DoomLoopMiddleware(AgentMiddleware[AgentState[ResponseT], ContextT, ResponseT]):
    """Detect repeated identical tool calls and prompt the user.

    Tracks a sliding window of the most-recent ``threshold`` tool-call
    signatures across the live request. When all entries match, raise
    a SurfSense-style HITL interrupt with ``permission="doom_loop"``.

    Args:
        threshold: How many consecutive identical signatures count as a
            doom loop. Default 3 (opencode parity).
    """

    def __init__(self, *, threshold: int = 3) -> None:
        super().__init__()
        if threshold < 2:
            raise ValueError("DoomLoopMiddleware threshold must be >= 2")
        self._threshold = threshold
        self.tools = []
        # Per-thread sliding windows. We can't put this in graph state
        # without state-schema gymnastics; for one process-lifetime it's
        # fine to keep an in-memory map keyed by thread_id.
        self._windows: dict[str, deque[str]] = {}

    @staticmethod
    def _thread_id_from_runtime(runtime: Runtime[ContextT]) -> str:
        """Resolve the thread id for sliding-window keying.

        Prefer LangGraph's ``get_config()`` (the only way to read
        ``RunnableConfig`` inside a node — :class:`Runtime` does NOT carry
        a ``config`` attribute). Fall back to ``runtime.config`` for unit
        tests that synthesize a config-bearing stub. Default
        ``"no_thread"`` is intentionally only used when both lookups fail
        — it would collapse all threads into one window so we keep the
        debug log loud.
        """

        def _from_dict(cfg: Any) -> str | None:
            if not isinstance(cfg, dict):
                return None
            tid = (cfg.get("configurable") or {}).get("thread_id")
            return str(tid) if tid is not None else None

        try:
            tid = _from_dict(get_config())
        except Exception:
            tid = None
        if tid is not None:
            return tid

        tid = _from_dict(getattr(runtime, "config", None))
        if tid is not None:
            return tid

        logger.debug(
            "DoomLoopMiddleware: no thread_id resolved from RunnableConfig; "
            "falling back to shared 'no_thread' window."
        )
        return "no_thread"

    def _window(self, thread_id: str) -> deque[str]:
        win = self._windows.get(thread_id)
        if win is None:
            win = deque(maxlen=self._threshold)
            self._windows[thread_id] = win
        return win

    def _detect(
        self, message: AIMessage, runtime: Runtime[ContextT]
    ) -> tuple[bool, list[str], dict[str, Any] | None]:
        if not message.tool_calls:
            return False, [], None

        thread_id = self._thread_id_from_runtime(runtime)
        window = self._window(thread_id)

        triggered_call: dict[str, Any] | None = None
        for call in message.tool_calls:
            name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
            args = call.get("args") if isinstance(call, dict) else getattr(call, "args", {})
            if not isinstance(name, str):
                continue
            sig = _signature(name, args)
            window.append(sig)
            if (
                len(window) >= self._threshold
                and len(set(window)) == 1
            ):
                triggered_call = {"name": name, "params": args or {}}
                break

        if triggered_call is None:
            return False, list(window), None
        return True, list(window), triggered_call

    def after_model(  # type: ignore[override]
        self,
        state: AgentState[ResponseT],
        runtime: Runtime[ContextT],
    ) -> dict[str, Any] | None:
        messages = state.get("messages") or []
        if not messages:
            return None
        last = messages[-1]
        if not isinstance(last, AIMessage):
            return None

        triggered, signatures, action = self._detect(last, runtime)
        if not triggered:
            return None

        logger.warning(
            "Doom loop detected: tool %s called %d times in a row (sig=%s)",
            action["name"] if action else "<unknown>",
            self._threshold,
            signatures[-1] if signatures else "<empty>",
        )

        # Tier 3b: interrupt.raised span with permission=doom_loop attribute
        # so dashboards can break out doom-loop interrupts from regular
        # permission asks via the ``interrupt.permission`` attribute.
        with ot.interrupt_span(
            interrupt_type="permission_ask",
            extra={
                "interrupt.permission": "doom_loop",
                "interrupt.threshold": self._threshold,
                "interrupt.tool": (action or {}).get("tool", "<unknown>"),
            },
        ):
            decision = interrupt(
                {
                    "type": "permission_ask",
                    "action": action or {"tool": "<unknown>", "params": {}},
                    "context": {
                        "permission": "doom_loop",
                        "recent_signatures": signatures,
                        "threshold": self._threshold,
                    },
                }
            )

        # Reset window so the next decision (continue/cancel) starts fresh.
        thread_id = self._thread_id_from_runtime(runtime)
        self._windows.pop(thread_id, None)

        # Decision shape mirrors ``tools/hitl.py``: {"decision_type": "..."}
        # If the user cancelled, jump to end. Otherwise return ``None`` so the
        # tool call proceeds. The frontend's exact reply names may differ —
        # we tolerate any shape that contains a string with "reject"/"cancel".
        if isinstance(decision, dict):
            kind = str(decision.get("decision_type") or decision.get("type") or "").lower()
            if "reject" in kind or "cancel" in kind:
                return {"jump_to": "end"}
        return None

    async def aafter_model(  # type: ignore[override]
        self,
        state: AgentState[ResponseT],
        runtime: Runtime[ContextT],
    ) -> dict[str, Any] | None:
        return self.after_model(state, runtime)


__all__ = [
    "DoomLoopMiddleware",
    "_signature",
]
