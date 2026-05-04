from __future__ import annotations

from typing import Any

from app.agents.multi_agent_chat.subagents.shared.permissions import (
    ToolsPermissions,
)

from .create_page import create_create_confluence_page_tool
from .delete_page import create_delete_confluence_page_tool
from .update_page import create_update_confluence_page_tool


def load_tools(*, dependencies: dict[str, Any] | None = None, **kwargs: Any) -> ToolsPermissions:
    resolved_dependencies = {**(dependencies or {}), **kwargs}
    session_dependencies = {
        "db_session": resolved_dependencies["db_session"],
        "search_space_id": resolved_dependencies["search_space_id"],
        "user_id": resolved_dependencies["user_id"],
        "connector_id": resolved_dependencies.get("connector_id"),
    }
    create = create_create_confluence_page_tool(**session_dependencies)
    update = create_update_confluence_page_tool(**session_dependencies)
    delete = create_delete_confluence_page_tool(**session_dependencies)
    return {
        "allow": [],
        "ask": [
            {"name": getattr(create, "name", "") or "", "tool": create},
            {"name": getattr(update, "name", "") or "", "tool": update},
            {"name": getattr(delete, "name", "") or "", "tool": delete},
        ],
    }
