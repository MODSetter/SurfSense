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
            {"name": "slack_search_channels"},
            {"name": "slack_search_messages"},
            {"name": "slack_search_users"},
            {"name": "slack_read_channel"},
            {"name": "slack_read_thread"},
        ],
        "ask": [
            {"name": "slack_send_message"},
        ],
    }
