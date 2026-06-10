"""``linear`` permission ruleset (rules over MCP tool names)."""

from __future__ import annotations

from app.agents.chat.multi_agent_chat.shared.permissions import Rule, Ruleset

NAME = "linear"

RULESET = Ruleset(
    origin=NAME,
    rules=[
        Rule(permission="list_issues", pattern="*", action="allow"),
        Rule(permission="get_issue", pattern="*", action="allow"),
        Rule(permission="list_my_issues", pattern="*", action="allow"),
        Rule(permission="list_issue_statuses", pattern="*", action="allow"),
        Rule(permission="list_issue_labels", pattern="*", action="allow"),
        Rule(permission="list_comments", pattern="*", action="allow"),
        Rule(permission="list_users", pattern="*", action="allow"),
        Rule(permission="get_user", pattern="*", action="allow"),
        Rule(permission="list_teams", pattern="*", action="allow"),
        Rule(permission="get_team", pattern="*", action="allow"),
        Rule(permission="list_projects", pattern="*", action="allow"),
        Rule(permission="get_project", pattern="*", action="allow"),
        Rule(permission="list_project_labels", pattern="*", action="allow"),
        Rule(permission="list_cycles", pattern="*", action="allow"),
        Rule(permission="list_documents", pattern="*", action="allow"),
        Rule(permission="get_document", pattern="*", action="allow"),
        Rule(permission="search_documentation", pattern="*", action="allow"),
        Rule(permission="save_issue", pattern="*", action="ask"),
    ],
)
