"""Build the permission-ask interrupt payload (LC HITL wire + SurfSense context)."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool

from app.agents.multi_agent_chat.subagents.shared.hitl.wire import (
    LC_DECISION_APPROVE,
    LC_DECISION_EDIT,
    LC_DECISION_REJECT,
    SURFSENSE_DECISION_ALWAYS,
    build_lc_hitl_payload,
)
from app.agents.new_chat.permissions import Rule

PERMISSION_ASK_INTERRUPT_TYPE = "permission_ask"

_PERMISSION_ASK_DECISIONS: list[str] = [
    LC_DECISION_APPROVE,
    LC_DECISION_REJECT,
    LC_DECISION_EDIT,
    SURFSENSE_DECISION_ALWAYS,
]


def _card_fields_from_tool(tool: BaseTool | None) -> dict[str, Any]:
    """Project the FE card's tool-scoped fields out of a BaseTool."""
    if tool is None:
        return {}
    metadata = getattr(tool, "metadata", None) or {}
    fields: dict[str, Any] = {}
    connector_id = metadata.get("mcp_connector_id")
    if connector_id is not None:
        fields["mcp_connector_id"] = connector_id
    connector_name = metadata.get("mcp_connector_name")
    if connector_name:
        fields["mcp_server"] = connector_name
    if tool.description:
        fields["tool_description"] = tool.description
    return fields


def build_permission_ask_payload(
    *,
    tool_name: str,
    args: dict[str, Any],
    patterns: list[str],
    rules: list[Rule],
    tool: BaseTool | None = None,
) -> dict[str, Any]:
    """Build the permission-ask interrupt payload.

    ``tool`` carries the FE card's tool-scoped fields (description, MCP
    connector). When omitted the card still renders, just without the
    "Always Allow against this connected account" surface.
    """
    context: dict[str, Any] = {
        "patterns": patterns,
        "rules": [
            {"permission": r.permission, "pattern": r.pattern, "action": r.action}
            for r in rules
        ],
        "always": patterns,
        **_card_fields_from_tool(tool),
    }
    return build_lc_hitl_payload(
        tool_name=tool_name,
        args=args,
        allowed_decisions=_PERMISSION_ASK_DECISIONS,
        interrupt_type=PERMISSION_ASK_INTERRUPT_TYPE,
        context=context,
    )


__all__ = ["PERMISSION_ASK_INTERRUPT_TYPE", "build_permission_ask_payload"]
