"""Jira MCP: which server tool names are allow vs ask."""

from __future__ import annotations

from app.agents.multi_agent_chat.subagents.shared.tool_kinds import (
    ToolsPermissions,
)

TOOLS_PERMISSIONS: ToolsPermissions = {
    "allow": [
        {"name": "getAccessibleAtlassianResources"},
        {"name": "getVisibleJiraProjects"},
        {"name": "searchJiraIssuesUsingJql"},
        {"name": "getJiraIssue"},
        {"name": "getJiraProjectIssueTypesMetadata"},
        {"name": "getJiraIssueTypeMetaWithFields"},
        {"name": "getTransitionsForJiraIssue"},
        {"name": "lookupJiraAccountId"},
    ],
    "ask": [
        {"name": "createJiraIssue"},
        {"name": "editJiraIssue"},
        {"name": "transitionJiraIssue"},
    ],
}
