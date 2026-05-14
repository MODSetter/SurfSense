"""Row builder for tools that self-gate via :func:`request_approval`.

The default ``kind`` is omitted on purpose: ``ToolPermissionItem`` defaults
to ``self_gated`` when ``kind`` is absent, so the row stays compact while
keeping the type system honest. Symmetric with
:mod:`hitl.approvals.middleware_gated.tool_row` so connector factories can
read the same way for either kind.
"""

from __future__ import annotations

from langchain_core.tools import BaseTool

from app.agents.multi_agent_chat.subagents.shared.tool_kinds import (
    ToolPermissionItem,
)


def self_gated_tool_permission_row(tool: BaseTool) -> ToolPermissionItem:
    """Build one allow/ask row for a self-gated tool (body calls ``request_approval``)."""
    return {"name": getattr(tool, "name", "") or "", "tool": tool}


__all__ = ["self_gated_tool_permission_row"]
