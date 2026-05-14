"""Build the permission-ask interrupt payload (LC HITL wire + SurfSense context).

The FE's PermissionCard renders from:

- Standard langchain fields (``action_requests``, ``review_configs``) — drive
  the action chrome and the parallel-HITL routing layer (``task_tool``,
  ``resume_routing``) that batches concurrent approvals.
- ``interrupt_type="permission_ask"`` — selects the permission card variant.
- ``context.patterns`` / ``context.rules`` — explain *why* the ask fired.
- ``context.always`` — the patterns the user can promote to a permanent
  allow rule with a single ``"always"`` reply.
"""

from __future__ import annotations

from typing import Any

from app.agents.multi_agent_chat.subagents.shared.hitl.wire import (
    LC_DECISION_APPROVE,
    LC_DECISION_EDIT,
    LC_DECISION_REJECT,
    SURFSENSE_DECISION_ALWAYS,
    build_lc_hitl_payload,
)
from app.agents.new_chat.permissions import Rule

PERMISSION_ASK_INTERRUPT_TYPE = "permission_ask"

# The full palette a permission card may surface: approve once, edit-then-
# approve, reject, or "always" to promote the matched pattern.
_PERMISSION_ASK_DECISIONS: list[str] = [
    LC_DECISION_APPROVE,
    LC_DECISION_REJECT,
    LC_DECISION_EDIT,
    SURFSENSE_DECISION_ALWAYS,
]


def build_permission_ask_payload(
    *,
    tool_name: str,
    args: dict[str, Any],
    patterns: list[str],
    rules: list[Rule],
) -> dict[str, Any]:
    """Build the permission-ask interrupt payload.

    Args:
        tool_name: The tool whose call is being reviewed.
        args: The tool call arguments shown in the card.
        patterns: Wildcard patterns the call matched (drives ``always``).
        rules: Matched ruleset entries surfaced for explainability.

    Returns:
        A dict suitable for ``langgraph.types.interrupt(...)`` carrying both
        the LC HITL standard fields and SurfSense-specific context.
    """
    context: dict[str, Any] = {
        "patterns": patterns,
        "rules": [
            {
                "permission": r.permission,
                "pattern": r.pattern,
                "action": r.action,
            }
            for r in rules
        ],
        "always": patterns,
    }
    return build_lc_hitl_payload(
        tool_name=tool_name,
        args=args,
        allowed_decisions=_PERMISSION_ASK_DECISIONS,
        interrupt_type=PERMISSION_ASK_INTERRUPT_TYPE,
        context=context,
    )


__all__ = ["PERMISSION_ASK_INTERRUPT_TYPE", "build_permission_ask_payload"]
