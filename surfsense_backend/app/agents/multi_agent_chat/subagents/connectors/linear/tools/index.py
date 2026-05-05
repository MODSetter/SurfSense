from __future__ import annotations

from typing import Any

from app.agents.multi_agent_chat.subagents.shared.permissions import (
    ToolsPermissions,
)

from .create_issue import create_create_linear_issue_tool
from .delete_issue import create_delete_linear_issue_tool
from .update_issue import create_update_linear_issue_tool


def load_tools(
    *, dependencies: dict[str, Any] | None = None, **kwargs: Any
) -> ToolsPermissions:
    d = {**(dependencies or {}), **kwargs}
    common = {
        "db_session": d["db_session"],
        "search_space_id": d["search_space_id"],
        "user_id": d["user_id"],
        "connector_id": d.get("connector_id"),
    }
    create = create_create_linear_issue_tool(**common)
    update = create_update_linear_issue_tool(**common)
    delete = create_delete_linear_issue_tool(**common)
    return {
        "allow": [],
        "ask": [
            {"name": getattr(create, "name", "") or "", "tool": create},
            {"name": getattr(update, "name", "") or "", "tool": update},
            {"name": getattr(delete, "name", "") or "", "tool": delete},
        ],
    }
