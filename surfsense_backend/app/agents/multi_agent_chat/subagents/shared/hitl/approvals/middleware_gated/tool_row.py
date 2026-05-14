"""Row builder tagging a tool for middleware-gated approval.

Used by MCP tool loading (``mcp_tools/index.py``) so each row carries
``kind="middleware_gated"`` and surfaces in :func:`middleware_gated_interrupt_on`.
Self-gated factories don't call this — they build rows inline with the
default ``kind`` (which collapses to self-gated).
"""

from __future__ import annotations

from langchain_core.tools import BaseTool

from app.agents.multi_agent_chat.subagents.shared.tool_kinds import (
    ToolPermissionItem,
)


def middleware_gated_tool_permission_row(tool: BaseTool) -> ToolPermissionItem:
    """Build one allow/ask row tagged ``kind="middleware_gated"``."""
    return {
        "name": getattr(tool, "name", "") or "",
        "tool": tool,
        "kind": "middleware_gated",
    }


__all__ = ["middleware_gated_tool_permission_row"]
