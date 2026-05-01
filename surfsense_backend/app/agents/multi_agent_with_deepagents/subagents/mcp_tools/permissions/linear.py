"""Linear MCP: which server tool names are allow vs ask."""

from __future__ import annotations

from app.agents.multi_agent_with_deepagents.subagents.shared.permissions import (
    ToolsPermissions,
)

_TOOLS_ALLOW = (
    "list_issues",
    "get_issue",
    "list_my_issues",
    "list_issue_statuses",
    "list_issue_labels",
    "list_comments",
    "list_users",
    "get_user",
    "list_teams",
    "get_team",
    "list_projects",
    "get_project",
    "list_project_labels",
    "list_cycles",
    "list_documents",
    "get_document",
    "search_documentation",
)

TOOLS_PERMISSIONS: ToolsPermissions = {
    "allow": [{"name": n} for n in _TOOLS_ALLOW],
    "ask": [{"name": "save_issue"}],
}
