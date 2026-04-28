"""
ToolCallNameRepairMiddleware — two-stage tool-name repair.

Mirrors ``opencode/packages/opencode/src/session/llm.ts:339-358`` plus
``opencode/packages/opencode/src/tool/invalid.ts``. Tier 1.7 in the
OpenCode-port plan.

Operation:
1. **Stage 1 — lowercase repair:** if a tool call's ``name`` is not in
   the registry but ``name.lower()`` is, rewrite in place. Catches
   models that emit ``Search`` instead of ``search``.
2. **Stage 2 — invalid fallback:** if still unmatched, rewrite the call
   to ``invalid`` with ``args={"tool": original_name, "error": <error>}``
   so the registered :func:`invalid_tool` returns the error to the model
   for self-correction.

Distinct from :class:`deepagents.middleware.PatchToolCallsMiddleware`,
which patches *dangling* tool calls (no matching ToolMessage) — that
class does not handle the wrong-name case at all.
"""

from __future__ import annotations

import difflib
import logging
from typing import Any

from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
    ContextT,
    ResponseT,
)
from langchain_core.messages import AIMessage
from langgraph.runtime import Runtime

from app.agents.new_chat.tools.invalid_tool import INVALID_TOOL_NAME

logger = logging.getLogger(__name__)


def _coerce_existing_tool_call(call: Any) -> dict[str, Any]:
    """Normalize a tool call entry to a mutable dict."""
    if isinstance(call, dict):
        return dict(call)
    return {
        "name": getattr(call, "name", None),
        "args": getattr(call, "args", {}),
        "id": getattr(call, "id", None),
        "type": "tool_call",
    }


class ToolCallNameRepairMiddleware(AgentMiddleware[AgentState[ResponseT], ContextT, ResponseT]):
    """Two-stage tool-name repair on the most recent ``AIMessage``.

    Args:
        registered_tool_names: Set of canonically-registered tool names.
            ``invalid`` should be in this set so the fallback dispatches.
        fuzzy_match_threshold: Optional ``difflib`` ratio (0–1) for the
            fuzzy-match step that runs *between* lowercase and invalid.
            Set to ``None`` to disable fuzzy matching (opencode parity).
    """

    def __init__(
        self,
        *,
        registered_tool_names: set[str],
        fuzzy_match_threshold: float | None = 0.85,
    ) -> None:
        super().__init__()
        self._registered = set(registered_tool_names)
        self._registered_lower = {name.lower(): name for name in self._registered}
        self._fuzzy_threshold = fuzzy_match_threshold
        self.tools = []

    def _registered_for_runtime(self, runtime: Runtime[ContextT]) -> set[str]:
        """Allow runtime overrides to expand the set (e.g. dynamic MCP tools)."""
        ctx_tools = getattr(runtime.context, "registered_tool_names", None)
        if isinstance(ctx_tools, (set, frozenset)):
            return self._registered | set(ctx_tools)
        if isinstance(ctx_tools, (list, tuple)):
            return self._registered | set(ctx_tools)
        return self._registered

    def _repair_one(
        self,
        call: dict[str, Any],
        registered: set[str],
    ) -> dict[str, Any]:
        name = call.get("name")
        if not isinstance(name, str):
            return call

        if name in registered:
            return call

        # Stage 1 — lowercase
        lowered = name.lower()
        if lowered in registered:
            call["name"] = lowered
            metadata = dict(call.get("response_metadata") or {})
            metadata.setdefault("repair", "lowercase")
            call["response_metadata"] = metadata
            return call

        # Optional fuzzy step (off by default for opencode parity)
        if self._fuzzy_threshold is not None:
            close = difflib.get_close_matches(
                name, registered, n=1, cutoff=self._fuzzy_threshold
            )
            if close:
                call["name"] = close[0]
                metadata = dict(call.get("response_metadata") or {})
                metadata.setdefault("repair", f"fuzzy:{name}->{close[0]}")
                call["response_metadata"] = metadata
                return call

        # Stage 2 — invalid fallback
        if INVALID_TOOL_NAME in registered:
            original_args = call.get("args") or {}
            error_msg = (
                f"Tool name '{name}' is not registered. "
                f"Original arguments were: {original_args!r}."
            )
            call["name"] = INVALID_TOOL_NAME
            call["args"] = {"tool": name, "error": error_msg}
            metadata = dict(call.get("response_metadata") or {})
            metadata.setdefault("repair", f"invalid_fallback:{name}")
            call["response_metadata"] = metadata
        else:
            logger.warning(
                "Could not repair unknown tool call %r; 'invalid' tool not registered",
                name,
            )
        return call

    def _maybe_repair(
        self,
        message: AIMessage,
        registered: set[str],
    ) -> AIMessage | None:
        if not message.tool_calls:
            return None

        new_calls: list[dict[str, Any]] = []
        any_changed = False
        for raw in message.tool_calls:
            call = _coerce_existing_tool_call(raw)
            before = (call.get("name"), call.get("args"))
            repaired = self._repair_one(call, registered)
            after = (repaired.get("name"), repaired.get("args"))
            if before != after:
                any_changed = True
            new_calls.append(repaired)

        if not any_changed:
            return None

        return message.model_copy(update={"tool_calls": new_calls})

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

        registered = self._registered_for_runtime(runtime)
        repaired = self._maybe_repair(last, registered)
        if repaired is None:
            return None
        return {"messages": [repaired]}

    async def aafter_model(  # type: ignore[override]
        self,
        state: AgentState[ResponseT],
        runtime: Runtime[ContextT],
    ) -> dict[str, Any] | None:
        return self.after_model(state, runtime)


__all__ = [
    "ToolCallNameRepairMiddleware",
]
