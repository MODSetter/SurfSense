"""``airtable`` permission ruleset (rules over MCP tool names)."""

from __future__ import annotations

from app.agents.multi_agent_chat.shared.permissions import Rule, Ruleset

NAME = "airtable"

RULESET = Ruleset(
    origin=NAME,
    rules=[
        Rule(permission="list_bases", pattern="*", action="allow"),
        Rule(permission="search_bases", pattern="*", action="allow"),
        Rule(permission="list_tables_for_base", pattern="*", action="allow"),
        Rule(permission="get_table_schema", pattern="*", action="allow"),
        Rule(permission="list_records_for_table", pattern="*", action="allow"),
        Rule(permission="search_records", pattern="*", action="allow"),
        Rule(permission="create_records_for_table", pattern="*", action="ask"),
        Rule(permission="update_records_for_table", pattern="*", action="ask"),
    ],
)
