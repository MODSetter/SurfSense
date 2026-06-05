"""Side-effectful entry point: pause the graph and return the permission decision.

Wraps :func:`langgraph.types.interrupt` with the OTel spans the SurfSense
dashboard expects, then projects the resume value through
:func:`normalize_permission_decision` so the middleware downstream only
sees the canonical permission-domain shape.

When ``emit_interrupt`` is ``False`` the call short-circuits to ``reject``;
this is used by non-interactive deployments where ``ask`` must not block.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool
from langgraph.types import interrupt

from app.agents.multi_agent_chat.shared.permissions import Rule
from app.observability import metrics as ot_metrics, otel as ot

from .decision import normalize_permission_decision
from .payload import PERMISSION_ASK_INTERRUPT_TYPE, build_permission_ask_payload


def request_permission_decision(
    *,
    tool_name: str,
    args: dict[str, Any],
    patterns: list[str],
    rules: list[Rule],
    emit_interrupt: bool,
    tool: BaseTool | None = None,
) -> dict[str, Any]:
    """Pause for an ``ask`` decision; return the canonical permission decision dict."""
    if not emit_interrupt:
        return {"decision_type": "reject"}

    payload = build_permission_ask_payload(
        tool_name=tool_name,
        args=args,
        patterns=patterns,
        rules=rules,
        tool=tool,
    )

    with (
        ot.permission_asked_span(
            permission=tool_name,
            pattern=patterns[0] if patterns else None,
            extra={"permission.patterns": list(patterns)},
        ),
        ot.interrupt_span(interrupt_type=PERMISSION_ASK_INTERRUPT_TYPE),
    ):
        ot_metrics.record_permission_ask(permission=tool_name)
        ot_metrics.record_interrupt(interrupt_type=PERMISSION_ASK_INTERRUPT_TYPE)
        decision = interrupt(payload)
    return normalize_permission_decision(decision)


__all__ = ["request_permission_decision"]
