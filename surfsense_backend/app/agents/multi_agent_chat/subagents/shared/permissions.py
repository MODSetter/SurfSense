"""Typed tool-permission rows: allow vs ask (``name`` + optional ``tool``)."""

from __future__ import annotations

from typing import Literal, NotRequired, TypedDict

from langchain_core.tools import BaseTool

# ``native`` rows self-gate via ``request_approval`` in the tool body;
# ``mcp`` rows are gated by ``HumanInTheLoopMiddleware`` via ``interrupt_on``.
ToolKind = Literal["native", "mcp"]


class ToolPermissionItem(TypedDict):
    """``name`` is always set; ``tool`` is present when a bound tool exists; ``kind`` defaults to ``native`` when absent."""

    name: str
    tool: NotRequired[BaseTool]
    kind: NotRequired[ToolKind]


class ToolsPermissions(TypedDict):
    """Same shape for native factories and MCP name-only policy rows."""

    allow: list[ToolPermissionItem]
    ask: list[ToolPermissionItem]


def tool_permission_row(tool: BaseTool) -> ToolPermissionItem:
    """Build one allow/ask row for a loaded tool."""
    return {"name": getattr(tool, "name", "") or "", "tool": tool}


def mcp_tool_permission_row(tool: BaseTool) -> ToolPermissionItem:
    """Build one allow/ask row tagged ``kind="mcp"`` so it routes through ``HumanInTheLoopMiddleware``."""
    return {"name": getattr(tool, "name", "") or "", "tool": tool, "kind": "mcp"}


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


def middleware_gated_interrupt_on(
    bucket: ToolsPermissions,
) -> dict[str, bool]:
    """``interrupt_on`` for ``ask`` rows whose bodies don't self-gate via ``request_approval``."""
    return {
        r["name"]: True
        for r in bucket["ask"]
        if r.get("name") and r.get("kind") == "mcp"
    }
