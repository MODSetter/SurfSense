from __future__ import annotations

from typing import Any

from app.agents.multi_agent_with_deepagents.subagents.shared.permissions import (
    ToolsPermissions,
)

from .create_file import create_create_google_drive_file_tool
from .trash_file import create_delete_google_drive_file_tool


def load_tools(*, dependencies: dict[str, Any] | None = None, **kwargs: Any) -> ToolsPermissions:
    d = {**(dependencies or {}), **kwargs}
    common = {
        "db_session": d["db_session"],
        "search_space_id": d["search_space_id"],
        "user_id": d["user_id"],
    }
    create = create_create_google_drive_file_tool(**common)
    delete = create_delete_google_drive_file_tool(**common)
    return {
        "allow": [],
        "ask": [
            {"name": getattr(create, "name", "") or "", "tool": create},
            {"name": getattr(delete, "name", "") or "", "tool": delete},
        ],
    }
