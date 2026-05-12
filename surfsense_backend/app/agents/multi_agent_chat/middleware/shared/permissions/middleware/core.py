"""``PermissionMiddleware`` — pattern-based allow/deny/ask with HITL fallback.

LangChain's :class:`HumanInTheLoopMiddleware` only supports a static
"this tool always asks" decision per tool. There's no rule-based
allow/deny/ask, no glob patterns, no per-space/per-thread overrides, and
no auto-deny synthesis.

This middleware layers OpenCode's wildcard-ruleset model on top of
SurfSense's ``interrupt({type, action, context})`` payload shape (see
:mod:`app.agents.new_chat.tools.hitl`) so the frontend keeps working
unchanged.

Per-tool-call flow inside :meth:`_process`:

1. Skip when the last message has no tool calls.
2. For each call, evaluate the rules. ``deny`` is replaced with a
   synthetic :class:`ToolMessage` carrying a typed
   :class:`StreamingError`. ``ask`` raises an interrupt via
   :mod:`interrupt.request`; the resulting decision is dispatched here:

   - ``once``  → keep the call as-is.
   - ``always`` → also extend the runtime ruleset.
   - ``reject`` (with feedback) → :class:`CorrectedError`.
   - ``reject`` (no feedback)   → :class:`RejectedError`.

   ``allow`` keeps the call unchanged.

3. Returns an updated ``AIMessage`` (tool calls minus the denied ones)
   plus any deny ``ToolMessage`` entries appended after it. Tool-list
   filtering at ``before_model`` is intentionally not done here — that
   would invalidate provider prompt-cache prefixes.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
    ContextT,
)
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.runtime import Runtime

from app.agents.new_chat.errors import CorrectedError, RejectedError
from app.agents.new_chat.permissions import Ruleset

from ..deny import build_deny_message
from ..interrupt.edit import merge_edited_args
from ..interrupt.request import request_permission_decision
from ..pattern_resolver import PatternResolver
from ..runtime_promote import persist_always
from .evaluation import evaluate_tool_call
from .ruleset_view import all_rulesets

logger = logging.getLogger(__name__)


class PermissionMiddleware(AgentMiddleware):  # type: ignore[type-arg]
    """Allow/deny/ask layer over the agent's tool calls.

    Args:
        rulesets: Layered rulesets to evaluate (earliest-to-latest wins).
            Typical layering: ``defaults < global < space < thread < runtime_approved``.
        pattern_resolvers: Optional per-tool callables that map ``args``
            to wildcard patterns. Tools without an entry use the bare
            tool name as the only pattern.
        runtime_ruleset: Mutable :class:`Ruleset` extended in-place when
            the user replies ``"always"``. Reused across calls in the
            same agent instance so newly-allowed rules apply downstream.
        always_emit_interrupt_payload: Set ``False`` to make ``ask``
            collapse to ``deny`` (for non-interactive deployments).
    """

    tools = ()

    def __init__(
        self,
        *,
        rulesets: list[Ruleset] | None = None,
        pattern_resolvers: dict[str, PatternResolver] | None = None,
        runtime_ruleset: Ruleset | None = None,
        always_emit_interrupt_payload: bool = True,
    ) -> None:
        super().__init__()
        self._static_rulesets: list[Ruleset] = list(rulesets or [])
        self._pattern_resolvers: dict[str, PatternResolver] = dict(
            pattern_resolvers or {}
        )
        self._runtime_ruleset: Ruleset = runtime_ruleset or Ruleset(
            origin="runtime_approved"
        )
        self._emit_interrupt = always_emit_interrupt_payload

    def _process(
        self,
        state: AgentState,
        runtime: Runtime[Any],
    ) -> dict[str, Any] | None:
        del runtime
        messages = state.get("messages") or []
        if not messages:
            return None
        last = messages[-1]
        if not isinstance(last, AIMessage) or not last.tool_calls:
            return None

        rulesets = all_rulesets(self._static_rulesets, self._runtime_ruleset)
        deny_messages: list[ToolMessage] = []
        kept_calls: list[dict[str, Any]] = []
        any_change = False

        for raw in last.tool_calls:
            call = (
                dict(raw)
                if isinstance(raw, dict)
                else {
                    "name": getattr(raw, "name", None),
                    "args": getattr(raw, "args", {}),
                    "id": getattr(raw, "id", None),
                    "type": "tool_call",
                }
            )
            name = call.get("name") or ""
            args = call.get("args") or {}
            action, patterns, rules = evaluate_tool_call(
                name, args, self._pattern_resolvers, rulesets
            )

            if action == "deny":
                deny_rule = next((r for r in rules if r.action == "deny"), rules[0])
                deny_messages.append(build_deny_message(call, deny_rule))
                any_change = True
                continue

            if action == "ask":
                decision = request_permission_decision(
                    tool_name=name,
                    args=args,
                    patterns=patterns,
                    rules=rules,
                    emit_interrupt=self._emit_interrupt,
                )
                kind = str(decision.get("decision_type") or "reject").lower()
                edited_args = decision.get("edited_args")
                if kind in ("once", "always"):
                    final_call = (
                        merge_edited_args(call, edited_args)
                        if isinstance(edited_args, dict) and edited_args
                        else call
                    )
                    if final_call is not call:
                        any_change = True
                    if kind == "always":
                        persist_always(self._runtime_ruleset, name, patterns)
                    kept_calls.append(final_call)
                elif kind == "reject":
                    feedback = decision.get("feedback")
                    if isinstance(feedback, str) and feedback.strip():
                        raise CorrectedError(feedback, tool=name)
                    raise RejectedError(
                        tool=name, pattern=patterns[0] if patterns else None
                    )
                else:
                    logger.warning(
                        "Unknown permission decision %r; treating as reject", kind
                    )
                    raise RejectedError(tool=name)
                continue

            kept_calls.append(call)

        if not any_change and len(kept_calls) == len(last.tool_calls):
            return None

        updated = last.model_copy(update={"tool_calls": kept_calls})
        result_messages: list[Any] = [updated]
        if deny_messages:
            result_messages.extend(deny_messages)
        return {"messages": result_messages}

    def after_model(  # type: ignore[override]
        self, state: AgentState, runtime: Runtime[ContextT]
    ) -> dict[str, Any] | None:
        return self._process(state, runtime)

    async def aafter_model(  # type: ignore[override]
        self, state: AgentState, runtime: Runtime[ContextT]
    ) -> dict[str, Any] | None:
        return self._process(state, runtime)


__all__ = ["PermissionMiddleware"]
