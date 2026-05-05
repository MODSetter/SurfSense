"""Jira MCP: which server tool names are allow vs ask."""

from __future__ import annotations

from app.agents.multi_agent_chat.subagents.shared.permissions import (
    ToolsPermissions,
)

TOOLS_PERMISSIONS: ToolsPermissions = {
    "allow": [
        {"name": "getAccessibleAtlassianResources"},
        {"name": "searchJiraIssuesUsingJql"},
        {"name": "getVisibleJiraProjects"},
        {"name": "getJiraProjectIssueTypesMetadata"},
    ],
    "ask": [
        {"name": "createJiraIssue"},
        {"name": "editJiraIssue"},
    ],
}
