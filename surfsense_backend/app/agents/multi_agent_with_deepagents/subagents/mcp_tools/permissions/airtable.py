"""Airtable MCP: which server tool names are allow vs ask."""

from __future__ import annotations

from app.agents.multi_agent_with_deepagents.subagents.shared.permissions import (
    ToolsPermissions,
)

TOOLS_PERMISSIONS: ToolsPermissions = {
    "allow": [
        {"name": "list_bases"},
        {"name": "list_tables_for_base"},
        {"name": "list_records_for_table"},
    ],
    "ask": [],
}
