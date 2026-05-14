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
