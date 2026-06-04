"""``PermissionMiddleware`` — pattern-based allow/deny/ask with HITL fallback.

LangChain's :class:`HumanInTheLoopMiddleware` only supports a static
"this tool always asks" decision per tool. There's no rule-based
allow/deny/ask, no glob patterns, no per-space/per-thread overrides, and
no auto-deny synthesis.

This middleware layers OpenCode's wildcard-ruleset model on top of the
unified langchain HITL wire format (see :mod:`hitl_wire`), so it sits
beside ``HumanInTheLoopMiddleware`` and self-gated approvals on a single
parallel-HITL routing layer in ``task_tool`` + ``resume_routing``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
    ContextT,
)
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.runtime import Runtime

from app.agents.shared.errors import CorrectedError, RejectedError
from app.agents.new_chat.permissions import Ruleset
from app.services.user_tool_allowlist import TrustedToolSaver

from ..ask.edit import merge_edited_args
from ..ask.request import request_permission_decision
from ..deny import build_deny_message
from .evaluation import evaluate_tool_call
from .pattern_resolver import PatternResolver
from .ruleset_view import all_rulesets
from .runtime_promote import persist_always

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _AlwaysPromotion:
    """A pending request to save an ``approve_always`` decision to the user's trust list."""

    connector_id: int
    tool_name: str


class PermissionMiddleware(AgentMiddleware):  # type: ignore[type-arg]
    """Allow/deny/ask layer over the agent's tool calls.

    Args:
        rulesets: Layered rulesets to evaluate (earliest-to-latest wins).
            Typical layering: ``defaults < global < space < thread < runtime_approved``.
        pattern_resolvers: Optional per-tool callables that map ``args``
            to wildcard patterns. Tools without an entry use the bare
            tool name as the only pattern.
        runtime_ruleset: Mutable :class:`Ruleset` extended in-place when
            the user replies ``"approve_always"``. Reused across calls in
            the same agent instance so newly-allowed rules apply downstream.
        always_emit_interrupt_payload: Set ``False`` to make ``ask``
            collapse to ``deny`` (for non-interactive deployments).
        tools_by_name: Map from tool name to :class:`BaseTool`, used to
            decorate ``ask`` interrupts with the tool's description and
            MCP metadata for the FE card.
        trusted_tool_saver: Async callback invoked on ``approve_always``
            decisions for MCP tools (those whose ``metadata`` carries an
            ``mcp_connector_id``). Without it the promotion only lives
            in-memory for the current agent instance.
    """

    tools = ()

    def __init__(
        self,
        *,
        rulesets: list[Ruleset] | None = None,
        pattern_resolvers: dict[str, PatternResolver] | None = None,
        runtime_ruleset: Ruleset | None = None,
        always_emit_interrupt_payload: bool = True,
        tools_by_name: dict[str, BaseTool] | None = None,
        trusted_tool_saver: TrustedToolSaver | None = None,
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
        self._tools_by_name: dict[str, BaseTool] = dict(tools_by_name or {})
        self._trusted_tool_saver: TrustedToolSaver | None = trusted_tool_saver

    def _process(
        self,
        state: AgentState,
        runtime: Runtime[Any],
    ) -> tuple[dict[str, Any] | None, list[_AlwaysPromotion]]:
        """Pure decision pass: returns ``(state_update, pending_promotions)``.

        Side effects performed here are in-memory only (rule promotion
        into ``runtime_ruleset``). DB writes for ``approve_always``
        decisions are queued as ``_AlwaysPromotion`` and flushed by the
        async hook.
        """
        del runtime
        messages = state.get("messages") or []
        if not messages:
            return None, []
        last = messages[-1]
        if not isinstance(last, AIMessage) or not last.tool_calls:
            return None, []

        rulesets = all_rulesets(self._static_rulesets, self._runtime_ruleset)
        deny_messages: list[ToolMessage] = []
        kept_calls: list[dict[str, Any]] = []
        promotions: list[_AlwaysPromotion] = []
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
                    tool=self._tools_by_name.get(name),
                )
                kind = str(decision.get("decision_type") or "reject").lower()
                edited_args = decision.get("edited_args")
                if kind in ("once", "approve_always"):
                    final_call = (
                        merge_edited_args(call, edited_args)
                        if isinstance(edited_args, dict) and edited_args
                        else call
                    )
                    if final_call is not call:
                        any_change = True
                    if kind == "approve_always":
                        persist_always(self._runtime_ruleset, name, patterns)
                        promotion = self._build_always_promotion(name)
                        if promotion is not None:
                            promotions.append(promotion)
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
            return None, promotions

        updated = last.model_copy(update={"tool_calls": kept_calls})
        result_messages: list[Any] = [updated]
        if deny_messages:
            result_messages.extend(deny_messages)
        return {"messages": result_messages}, promotions

    def _build_always_promotion(self, tool_name: str) -> _AlwaysPromotion | None:
        """Return a save request iff the tool exposes an ``mcp_connector_id``."""
        tool = self._tools_by_name.get(tool_name)
        metadata = getattr(tool, "metadata", None) or {}
        connector_id = metadata.get("mcp_connector_id")
        if not isinstance(connector_id, int):
            return None
        return _AlwaysPromotion(connector_id=connector_id, tool_name=tool_name)

    def after_model(  # type: ignore[override]
        self, state: AgentState, runtime: Runtime[ContextT]
    ) -> dict[str, Any] | None:
        update, _ = self._process(state, runtime)
        return update

    async def aafter_model(  # type: ignore[override]
        self, state: AgentState, runtime: Runtime[ContextT]
    ) -> dict[str, Any] | None:
        update, promotions = self._process(state, runtime)
        if self._trusted_tool_saver is not None:
            for promotion in promotions:
                await self._trusted_tool_saver(
                    promotion.connector_id, promotion.tool_name
                )
        return update


__all__ = ["PermissionMiddleware"]
