"""Typed tool-permission rows: allow vs ask (``name`` + optional ``tool``)."""

from __future__ import annotations

from typing import NotRequired, TypedDict

from langchain_core.tools import BaseTool


class ToolPermissionItem(TypedDict):
    """``name`` is always set; ``tool`` is present when a bound tool exists."""

    name: str
    tool: NotRequired[BaseTool]


class ToolsPermissions(TypedDict):
    """Same shape for native factories and MCP name-only policy rows."""

    allow: list[ToolPermissionItem]
    ask: list[ToolPermissionItem]


def tool_permission_row(tool: BaseTool) -> ToolPermissionItem:
    """Build one allow/ask row for a loaded tool."""
    return {"name": getattr(tool, "name", "") or "", "tool": tool}


def merge_tools_permissions(
    base: ToolsPermissions,
    extra: ToolsPermissions | None,
) -> ToolsPermissions:
    """Concatenate allow/ask lists (e.g. native factory + MCP bucket) before building HITL maps."""
    if not extra:
        return base
    return {
        "allow": [*base["allow"], *extra["allow"]],
        "ask": [*base["ask"], *extra["ask"]],
    }
