"""Slack MCP: which server tool names are allow vs ask."""

from __future__ import annotations

from app.agents.multi_agent_chat.subagents.shared.permissions import (
    ToolsPermissions,
)

TOOLS_PERMISSIONS: ToolsPermissions = {
    "allow": [
        {"name": "slack_search_channels"},
        {"name": "slack_search_messages"},
        {"name": "slack_search_users"},
        {"name": "slack_read_channel"},
        {"name": "slack_read_thread"},
    ],
    "ask": [
        {"name": "slack_send_message"},
    ],
}
