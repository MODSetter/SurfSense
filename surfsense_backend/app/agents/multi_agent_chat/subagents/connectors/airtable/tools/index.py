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
            {"name": "list_bases"},
            {"name": "search_bases"},
            {"name": "list_tables_for_base"},
            {"name": "get_table_schema"},
            {"name": "list_records_for_table"},
            {"name": "search_records"},
        ],
        "ask": [
            {"name": "create_records_for_table"},
            {"name": "update_records_for_table"},
        ],
    }
