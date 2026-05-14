"""Cross-kind primitives for tool permission rows.

Subagents classify their tools into ``allow`` and ``ask`` buckets, and each
row may be either *self-gated* (the tool body calls
:func:`request_approval`) or *middleware-gated* (a middleware intercepts
the call). This module owns the shared types both kinds need:

- :data:`ToolKind` — the discriminator literal.
- :class:`ToolPermissionItem` — one row in an allow/ask bucket.
- :class:`ToolsPermissions` — the bucket pair.
- :func:`merge_tools_permissions` — concatenates two buckets (typically a
  self-gated factory bucket and a middleware-gated MCP bucket).

Kind-specific helpers live under ``hitl/approvals/`` next to their gating
mechanism:

- ``hitl/approvals/self_gated/`` — body-level ``request_approval`` primitive.
- ``hitl/approvals/middleware_gated/`` — row builder + ``interrupt_on`` map.
"""

from __future__ import annotations

from typing import Literal, NotRequired, TypedDict

from langchain_core.tools import BaseTool

ToolKind = Literal["self_gated", "middleware_gated"]


class ToolPermissionItem(TypedDict):
    """One allow/ask row.

    ``name`` is always set; ``tool`` is present when a bound BaseTool exists
    (absent for name-only MCP policy rows). ``kind`` defaults to
    ``self_gated`` when absent so existing connector factories keep working
    without explicit tagging.
    """

    name: str
    tool: NotRequired[BaseTool]
    kind: NotRequired[ToolKind]


class ToolsPermissions(TypedDict):
    """Allow/ask buckets shared by self-gated factories and middleware-gated MCP rows."""

    allow: list[ToolPermissionItem]
    ask: list[ToolPermissionItem]


def merge_tools_permissions(
    base: ToolsPermissions,
    extra: ToolsPermissions | None,
) -> ToolsPermissions:
    """Concatenate allow/ask lists (e.g. self-gated factory + middleware-gated MCP) before building HITL maps."""
    if not extra:
        return base
    return {
        "allow": [*base["allow"], *extra["allow"]],
        "ask": [*base["ask"], *extra["ask"]],
    }


__all__ = [
    "ToolKind",
    "ToolPermissionItem",
    "ToolsPermissions",
    "merge_tools_permissions",
]
