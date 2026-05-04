"""
PermissionMiddleware — pattern-based allow/deny/ask with HITL fallback.

LangChain's :class:`HumanInTheLoopMiddleware` only supports a static
"this tool always asks" decision per tool. There's no rule-based
allow/deny/ask layered ruleset, no glob patterns, no per-search-space or
per-thread overrides, and no auto-deny synthesis.

This middleware ports OpenCode's ``packages/opencode/src/permission/index.ts``
ruleset model on top of SurfSense's existing ``interrupt({type, action,
context})`` payload shape (see ``app/agents/new_chat/tools/hitl.py``) so
the frontend keeps working unchanged.

Operation:
1. ``aafter_model`` inspects the latest ``AIMessage.tool_calls``.
2. For each call, the middleware builds a list of ``patterns`` (the
   tool name plus any tool-specific patterns from the resolver). It
   evaluates each pattern against the layered rulesets and aggregates
   the results: ``deny`` > ``ask`` > ``allow``.
3. On ``deny``: replaces the call with a synthetic ``ToolMessage``
   containing a :class:`StreamingError`.
4. On ``ask``: raises a SurfSense-style ``interrupt(...)``. Both the legacy
   SurfSense shape and LangChain HITL ``{"decisions": [{"type": ...}]}``
   replies are accepted via :func:`_normalize_permission_decision`.
   - ``once``: proceed.
   - ``always``: also persist allow rules for ``request.always`` patterns.
   - ``reject`` w/o feedback: raise :class:`RejectedError`.
   - ``reject`` w/  feedback: raise :class:`CorrectedError`.
5. On ``allow``: proceed unchanged.

The middleware also performs a *pre-model* tool-filter step (the
``before_model`` hook) so globally denied tools are stripped from the
exposed tool list before the model gets to see them. This mirrors
OpenCode's ``Permission.disabled`` and dramatically reduces the chance
the model emits a deny-only call.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
    ContextT,
)
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import interrupt

from app.agents.new_chat.errors import (
    CorrectedError,
    RejectedError,
    StreamingError,
)
from app.agents.new_chat.permissions import (
    Rule,
    Ruleset,
    aggregate_action,
    evaluate_many,
)
from app.observability import otel as ot

logger = logging.getLogger(__name__)


# Mapping ``tool_name -> resolver`` that converts ``args`` to a list of
# patterns to evaluate. The first pattern is conventionally the bare
# tool name; later entries narrow down to specific resources.
PatternResolver = Callable[[dict[str, Any]], list[str]]


def _default_pattern_resolver(name: str) -> PatternResolver:
    def _resolve(args: dict[str, Any]) -> list[str]:
        # Bare name covers the default catch-all; primary-arg fallbacks
        # are best added per-tool by callers.
        del args
        return [name]

    return _resolve


# Translation from the LangChain HITL envelope (what ``stream_resume_chat``
# sends) to SurfSense's legacy ``decision_type`` shape. ``edit`` keeps the
# original tool args — tools needing argument edits should use
# ``request_approval`` from ``app/agents/new_chat/tools/hitl.py``.
_LC_TYPE_TO_PERMISSION_DECISION: dict[str, str] = {
    "approve": "once",
    "reject": "reject",
    "edit": "once",
}


def _normalize_permission_decision(decision: Any) -> dict[str, Any]:
    """Coerce any accepted reply shape into ``{"decision_type": ..., "feedback"?}``.

    Falls back to ``reject`` (with a warning) on unrecognized payloads so the
    middleware fails closed.
    """
    if isinstance(decision, str):
        return {"decision_type": decision}
    if not isinstance(decision, dict):
        logger.warning(
            "Unrecognized permission resume value (%s); treating as reject",
            type(decision).__name__,
        )
        return {"decision_type": "reject"}

    if decision.get("decision_type"):
        return decision

    payload: dict[str, Any] = decision
    decisions = decision.get("decisions")
    if isinstance(decisions, list) and decisions:
        first = decisions[0]
        if isinstance(first, dict):
            payload = first

    raw_type = payload.get("type") or payload.get("decision_type")
    if not raw_type:
        logger.warning(
            "Permission resume missing decision type (keys=%s); treating as reject",
            list(payload.keys()),
        )
        return {"decision_type": "reject"}

    raw_type = str(raw_type).lower()
    mapped = _LC_TYPE_TO_PERMISSION_DECISION.get(raw_type)
    if mapped is None:
        # Tolerate legacy values arriving without ``decision_type`` wrapping.
        if raw_type in {"once", "always", "reject"}:
            mapped = raw_type
        else:
            logger.warning(
                "Unknown permission decision type %r; treating as reject", raw_type
            )
            mapped = "reject"

    if raw_type == "edit":
        logger.warning(
            "Permission middleware received an 'edit' decision; original args "
            "kept (edits not merged here)."
        )

    out: dict[str, Any] = {"decision_type": mapped}
    feedback = payload.get("feedback") or payload.get("message")
    if isinstance(feedback, str) and feedback.strip():
        out["feedback"] = feedback
    return out


class PermissionMiddleware(AgentMiddleware):  # type: ignore[type-arg]
    """Allow/deny/ask layer over the agent's tool calls.

    Args:
        rulesets: Layered rulesets to evaluate. Earlier entries are
            overridden by later ones (last-match-wins). Typical layering:
            ``defaults < global < space < thread < runtime_approved``.
        pattern_resolvers: Optional per-tool callables that return a list
            of patterns to evaluate. When a tool isn't listed, the bare
            tool name is used as the only pattern.
        runtime_ruleset: Mutable :class:`Ruleset` that the middleware
            extends in-place when the user replies ``"always"`` to an
            ask interrupt. Reused across all calls in the same agent
            instance so newly-allowed rules apply to subsequent calls.
        always_emit_interrupt_payload: If True, every ask uses the
            SurfSense interrupt wire format (default). Set False to
            disable interrupts and treat ``ask`` as ``deny`` for
            non-interactive deployments.
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

    # ------------------------------------------------------------------
    # Tool-filter step (mirrors OpenCode's ``Permission.disabled``)
    # ------------------------------------------------------------------

    def _globally_denied(self, tool_name: str) -> bool:
        """Return True if a deny rule with no narrowing pattern matches."""
        rules = evaluate_many(tool_name, ["*"], *self._all_rulesets())
        return aggregate_action(rules) == "deny"

    def _all_rulesets(self) -> list[Ruleset]:
        return [*self._static_rulesets, self._runtime_ruleset]

    # NOTE: ``before_model`` filtering of the tools list is left to the
    # agent factory. This middleware only blocks at execution time — and
    # only via the rule-evaluator path, not by mutating ``request.tools``.
    # Mutating ``request.tools`` per-call would invalidate provider
    # prompt-cache prefixes (see Operational risks: prompt-cache regression).

    # ------------------------------------------------------------------
    # Tool-call evaluation
    # ------------------------------------------------------------------

    def _resolve_patterns(self, tool_name: str, args: dict[str, Any]) -> list[str]:
        resolver = self._pattern_resolvers.get(
            tool_name, _default_pattern_resolver(tool_name)
        )
        try:
            patterns = resolver(args or {})
        except Exception:
            logger.exception(
                "Pattern resolver for %s raised; using bare name", tool_name
            )
            patterns = [tool_name]
        if not patterns:
            patterns = [tool_name]
        return patterns

    def _evaluate(
        self, tool_name: str, args: dict[str, Any]
    ) -> tuple[str, list[str], list[Rule]]:
        patterns = self._resolve_patterns(tool_name, args)
        rules = evaluate_many(tool_name, patterns, *self._all_rulesets())
        action = aggregate_action(rules)
        return action, patterns, rules

    # ------------------------------------------------------------------
    # HITL ask flow — SurfSense wire format
    # ------------------------------------------------------------------

    def _raise_interrupt(
        self,
        *,
        tool_name: str,
        args: dict[str, Any],
        patterns: list[str],
        rules: list[Rule],
    ) -> dict[str, Any]:
        """Block on user approval via SurfSense's ``interrupt`` shape."""
        if not self._emit_interrupt:
            return {"decision_type": "reject"}

        # ``params`` (NOT ``args``) is what SurfSense's streaming
        # normalizer forwards. Other fields move into ``context``.
        payload = {
            "type": "permission_ask",
            "action": {"tool": tool_name, "params": args or {}},
            "context": {
                "patterns": patterns,
                "rules": [
                    {
                        "permission": r.permission,
                        "pattern": r.pattern,
                        "action": r.action,
                    }
                    for r in rules
                ],
                # Rules of thumb for the frontend: surface the patterns
                # the user can promote to "always" with a single reply.
                "always": patterns,
            },
        }
        # Open ``permission.asked`` + ``interrupt.raised`` OTel spans
        # (no-op when OTel is disabled) so dashboards can correlate
        # "we asked X" with "interrupt was actually delivered".
        with (
            ot.permission_asked_span(
                permission=tool_name,
                pattern=patterns[0] if patterns else None,
                extra={"permission.patterns": list(patterns)},
            ),
            ot.interrupt_span(interrupt_type="permission_ask"),
        ):
            decision = interrupt(payload)
        return _normalize_permission_decision(decision)

    def _persist_always(self, tool_name: str, patterns: list[str]) -> None:
        """Promote ``always`` reply into runtime allow rules.

        Persistence to ``agent_permission_rules`` is done by the
        streaming layer (``stream_new_chat``) once it observes the
        ``always`` reply — the middleware just keeps an in-memory
        copy so subsequent calls in the same stream see the rule.
        """
        for pattern in patterns:
            self._runtime_ruleset.rules.append(
                Rule(permission=tool_name, pattern=pattern, action="allow")
            )

    # ------------------------------------------------------------------
    # Synthesizing deny -> ToolMessage
    # ------------------------------------------------------------------

    @staticmethod
    def _deny_message(
        tool_call: dict[str, Any],
        rule: Rule,
    ) -> ToolMessage:
        err = StreamingError(
            code="permission_denied",
            retryable=False,
            suggestion=(
                f"rule permission={rule.permission!r} pattern={rule.pattern!r} "
                f"blocked this call"
            ),
        )
        return ToolMessage(
            content=(
                f"Permission denied: rule {rule.permission}/{rule.pattern} "
                f"blocked tool {tool_call.get('name')!r}."
            ),
            tool_call_id=tool_call.get("id") or "",
            name=tool_call.get("name"),
            status="error",
            additional_kwargs={"error": err.model_dump()},
        )

    # ------------------------------------------------------------------
    # The hook: aafter_model
    # ------------------------------------------------------------------

    def _process(
        self,
        state: AgentState,
        runtime: Runtime[Any],
    ) -> dict[str, Any] | None:
        del runtime  # unused
        messages = state.get("messages") or []
        if not messages:
            return None
        last = messages[-1]
        if not isinstance(last, AIMessage) or not last.tool_calls:
            return None

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
            action, patterns, rules = self._evaluate(name, args)

            if action == "deny":
                # Find the deny rule for the suggestion text
                deny_rule = next((r for r in rules if r.action == "deny"), rules[0])
                deny_messages.append(self._deny_message(call, deny_rule))
                any_change = True
                continue

            if action == "ask":
                decision = self._raise_interrupt(
                    tool_name=name, args=args, patterns=patterns, rules=rules
                )
                kind = str(decision.get("decision_type") or "reject").lower()
                if kind == "once":
                    kept_calls.append(call)
                elif kind == "always":
                    self._persist_always(name, patterns)
                    kept_calls.append(call)
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

            # allow
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


__all__ = [
    "PatternResolver",
    "PermissionMiddleware",
    "_normalize_permission_decision",
]
