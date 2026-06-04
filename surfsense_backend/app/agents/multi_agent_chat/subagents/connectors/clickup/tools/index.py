"""``clickup`` permission ruleset (rules over MCP tool names)."""

from __future__ import annotations

from app.agents.shared.permissions import Rule, Ruleset

NAME = "clickup"

RULESET = Ruleset(
    origin=NAME,
    rules=[
        Rule(permission="clickup_search", pattern="*", action="allow"),
        Rule(permission="clickup_get_task", pattern="*", action="allow"),
        Rule(permission="clickup_get_workspace_hierarchy", pattern="*", action="allow"),
        Rule(permission="clickup_get_list", pattern="*", action="allow"),
        Rule(permission="clickup_find_member_by_name", pattern="*", action="allow"),
        Rule(permission="clickup_create_task", pattern="*", action="ask"),
        Rule(permission="clickup_update_task", pattern="*", action="ask"),
    ],
)
