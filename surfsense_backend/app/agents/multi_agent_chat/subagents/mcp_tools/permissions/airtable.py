"""Airtable MCP: which server tool names are allow vs ask."""

from __future__ import annotations

from app.agents.multi_agent_chat.subagents.shared.permissions import (
    ToolsPermissions,
)

TOOLS_PERMISSIONS: ToolsPermissions = {
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
