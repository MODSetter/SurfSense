"""Bundled MCP allow/ask name rows per connector agent (MCP-backed routes only)."""

from __future__ import annotations

from app.agents.multi_agent_with_deepagents.subagents.shared.permissions import (
    ToolsPermissions,
)

from .airtable import TOOLS_PERMISSIONS as _AIRTABLE
from .clickup import TOOLS_PERMISSIONS as _CLICKUP
from .jira import TOOLS_PERMISSIONS as _JIRA
from .linear import TOOLS_PERMISSIONS as _LINEAR
from .slack import TOOLS_PERMISSIONS as _SLACK

TOOLS_PERMISSIONS_BY_AGENT: dict[str, ToolsPermissions] = {
    "airtable": _AIRTABLE,
    "clickup": _CLICKUP,
    "jira": _JIRA,
    "linear": _LINEAR,
    "slack": _SLACK,
}

__all__ = ["TOOLS_PERMISSIONS_BY_AGENT"]
