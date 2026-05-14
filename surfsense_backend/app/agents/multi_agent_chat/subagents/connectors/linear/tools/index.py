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
            {"name": "list_issues"},
            {"name": "get_issue"},
            {"name": "list_my_issues"},
            {"name": "list_issue_statuses"},
            {"name": "list_issue_labels"},
            {"name": "list_comments"},
            {"name": "list_users"},
            {"name": "get_user"},
            {"name": "list_teams"},
            {"name": "get_team"},
            {"name": "list_projects"},
            {"name": "get_project"},
            {"name": "list_project_labels"},
            {"name": "list_cycles"},
            {"name": "list_documents"},
            {"name": "get_document"},
            {"name": "search_documentation"},
        ],
        "ask": [
            {"name": "save_issue"}
        ],
    }
