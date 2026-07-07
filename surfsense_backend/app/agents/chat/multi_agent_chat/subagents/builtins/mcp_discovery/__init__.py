"""``mcp_discovery`` builtin subagent: the user's connected apps via MCP.

Consolidates every MCP-backed connector (Slack, Jira, Linear, ClickUp,
Airtable, Notion, Confluence, generic user MCP servers) plus the interim
native Gmail/Calendar tools behind a single subagent. Tools are injected
directly (opencode/hermes pattern) so the tool-name-keyed permission and
"Always Allow" systems keep working unchanged.
"""
