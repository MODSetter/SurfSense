from __future__ import annotations

from typing import Any

from app.agents.multi_agent_chat.subagents.shared.hitl.approvals.self_gated import (
    self_gated_tool_permission_row,
)
from app.agents.multi_agent_chat.subagents.shared.tool_kinds import (
    ToolsPermissions,
)

from .create_event import create_create_calendar_event_tool
from .delete_event import create_delete_calendar_event_tool
from .search_events import create_search_calendar_events_tool
from .update_event import create_update_calendar_event_tool


def load_tools(
    *, dependencies: dict[str, Any] | None = None, **kwargs: Any
) -> ToolsPermissions:
    resolved_dependencies = {**(dependencies or {}), **kwargs}
    session_dependencies = {
        "db_session": resolved_dependencies["db_session"],
        "search_space_id": resolved_dependencies["search_space_id"],
        "user_id": resolved_dependencies["user_id"],
    }
    search = create_search_calendar_events_tool(**session_dependencies)
    create = create_create_calendar_event_tool(**session_dependencies)
    update = create_update_calendar_event_tool(**session_dependencies)
    delete = create_delete_calendar_event_tool(**session_dependencies)
    return {
        "allow": [self_gated_tool_permission_row(search)],
        "ask": [
            self_gated_tool_permission_row(create),
            self_gated_tool_permission_row(update),
            self_gated_tool_permission_row(delete),
        ],
    }
