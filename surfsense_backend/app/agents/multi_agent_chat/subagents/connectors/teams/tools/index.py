from __future__ import annotations

from typing import Any

from app.agents.multi_agent_chat.subagents.shared.hitl.approvals.self_gated import (
    self_gated_tool_permission_row,
)
from app.agents.multi_agent_chat.subagents.shared.tool_kinds import (
    ToolsPermissions,
)

from .list_channels import create_list_teams_channels_tool
from .read_messages import create_read_teams_messages_tool
from .send_message import create_send_teams_message_tool


def load_tools(
    *, dependencies: dict[str, Any] | None = None, **kwargs: Any
) -> ToolsPermissions:
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
            self_gated_tool_permission_row(list_ch),
            self_gated_tool_permission_row(read_msg),
        ],
        "ask": [self_gated_tool_permission_row(send)],
    }
