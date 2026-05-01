from __future__ import annotations

from typing import Any

from app.agents.multi_agent_with_deepagents.subagents.shared.permissions import (
    ToolsPermissions,
)

from .list_channels import create_list_teams_channels_tool
from .read_messages import create_read_teams_messages_tool
from .send_message import create_send_teams_message_tool


def load_tools(*, dependencies: dict[str, Any] | None = None, **kwargs: Any) -> ToolsPermissions:
    d = {**(dependencies or {}), **kwargs}
    common = {
        "db_session": d["db_session"],
        "search_space_id": d["search_space_id"],
        "user_id": d["user_id"],
    }
    list_ch = create_list_teams_channels_tool(**common)
    read_msg = create_read_teams_messages_tool(**common)
    send = create_send_teams_message_tool(**common)
    return {
        "allow": [
            {"name": getattr(list_ch, "name", "") or "", "tool": list_ch},
            {"name": getattr(read_msg, "name", "") or "", "tool": read_msg},
        ],
        "ask": [{"name": getattr(send, "name", "") or "", "tool": send}],
    }
