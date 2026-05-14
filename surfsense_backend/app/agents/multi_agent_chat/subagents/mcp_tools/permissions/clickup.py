"""ClickUp MCP: which server tool names are allow vs ask."""

from __future__ import annotations

from app.agents.multi_agent_chat.subagents.shared.tool_kinds import (
    ToolsPermissions,
)

TOOLS_PERMISSIONS: ToolsPermissions = {
    "allow": [
        {"name": "clickup_search"},
        {"name": "clickup_get_task"},
        {"name": "clickup_get_workspace_hierarchy"},
        {"name": "clickup_get_list"},
        {"name": "clickup_find_member_by_name"},
    ],
    "ask": [
        {"name": "clickup_create_task"},
        {"name": "clickup_update_task"},
    ],
}
