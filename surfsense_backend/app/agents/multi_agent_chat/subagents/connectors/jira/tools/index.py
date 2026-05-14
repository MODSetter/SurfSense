"""``jira`` permission ruleset (rules over MCP tool names)."""

from __future__ import annotations

from app.agents.new_chat.permissions import Rule, Ruleset

NAME = "jira"

RULESET = Ruleset(
    origin=NAME,
    rules=[
        Rule(permission="getAccessibleAtlassianResources", pattern="*", action="allow"),
        Rule(permission="getVisibleJiraProjects", pattern="*", action="allow"),
        Rule(permission="searchJiraIssuesUsingJql", pattern="*", action="allow"),
        Rule(permission="getJiraIssue", pattern="*", action="allow"),
        Rule(permission="getJiraProjectIssueTypesMetadata", pattern="*", action="allow"),
        Rule(permission="getJiraIssueTypeMetaWithFields", pattern="*", action="allow"),
        Rule(permission="getTransitionsForJiraIssue", pattern="*", action="allow"),
        Rule(permission="lookupJiraAccountId", pattern="*", action="allow"),
        Rule(permission="createJiraIssue", pattern="*", action="ask"),
        Rule(permission="editJiraIssue", pattern="*", action="ask"),
        Rule(permission="transitionJiraIssue", pattern="*", action="ask"),
    ],
)
