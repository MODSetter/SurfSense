from __future__ import annotations

from typing import Any

from app.agents.multi_agent_chat.subagents.shared.tool_kinds import (
    ToolsPermissions,
)


def load_tools(
    *, dependencies: dict[str, Any] | None = None, **kwargs: Any
) -> ToolsPermissions:
    _ = {**(dependencies or {}), **kwargs}
    return {
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
