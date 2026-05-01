"""Map connector type strings to the agent route key used for tools and MCP slices."""

from __future__ import annotations

CONNECTOR_TYPE_TO_CONNECTOR_AGENT_MAPS: dict[str, str] = {
    "GOOGLE_GMAIL_CONNECTOR": "gmail",
    "COMPOSIO_GMAIL_CONNECTOR": "gmail",
    "GOOGLE_CALENDAR_CONNECTOR": "calendar",
    "COMPOSIO_GOOGLE_CALENDAR_CONNECTOR": "calendar",
    "DISCORD_CONNECTOR": "discord",
    "TEAMS_CONNECTOR": "teams",
    "LUMA_CONNECTOR": "luma",
    "LINEAR_CONNECTOR": "linear",
    "JIRA_CONNECTOR": "jira",
    "CLICKUP_CONNECTOR": "clickup",
    "SLACK_CONNECTOR": "slack",
    "AIRTABLE_CONNECTOR": "airtable",
}
