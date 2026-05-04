from __future__ import annotations

from typing import Any

from app.agents.multi_agent_chat.subagents.shared.permissions import (
    ToolsPermissions,
)

from .create_event import create_create_luma_event_tool
from .list_events import create_list_luma_events_tool
from .read_event import create_read_luma_event_tool


def load_tools(*, dependencies: dict[str, Any] | None = None, **kwargs: Any) -> ToolsPermissions:
    d = {**(dependencies or {}), **kwargs}
    common = {
        "db_session": d["db_session"],
        "search_space_id": d["search_space_id"],
        "user_id": d["user_id"],
    }
    list_ev = create_list_luma_events_tool(**common)
    read_ev = create_read_luma_event_tool(**common)
    create = create_create_luma_event_tool(**common)
    return {
        "allow": [
            {"name": getattr(list_ev, "name", "") or "", "tool": list_ev},
            {"name": getattr(read_ev, "name", "") or "", "tool": read_ev},
        ],
        "ask": [{"name": getattr(create, "name", "") or "", "tool": create}],
    }
