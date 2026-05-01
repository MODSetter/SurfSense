"""Slack MCP: which server tool names are allow vs ask."""

from __future__ import annotations

from app.agents.multi_agent_with_deepagents.subagents.shared.permissions import (
    ToolsPermissions,
)

TOOLS_PERMISSIONS: ToolsPermissions = {
    "allow": [
        {"name": "slack_search_channels"},
        {"name": "slack_read_channel"},
        {"name": "slack_read_thread"},
    ],
    "ask": [],
}
