"""Connector-type to subagent name; subagent name to availability tokens for build_subagents."""

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
    "NOTION_CONNECTOR": "notion",
    "CONFLUENCE_CONNECTOR": "confluence",
    "GOOGLE_DRIVE_CONNECTOR": "google_drive",
    "COMPOSIO_GOOGLE_DRIVE_CONNECTOR": "google_drive",
    "DROPBOX_CONNECTOR": "dropbox",
    "ONEDRIVE_CONNECTOR": "onedrive",
}

SUBAGENT_TO_REQUIRED_CONNECTOR_MAP: dict[str, frozenset[str]] = {
    "deliverables": frozenset(),
    "airtable": frozenset({"AIRTABLE_CONNECTOR"}),
    "calendar": frozenset({"GOOGLE_CALENDAR_CONNECTOR"}),
    "clickup": frozenset({"CLICKUP_CONNECTOR"}),
    "confluence": frozenset({"CONFLUENCE_CONNECTOR"}),
    "discord": frozenset({"DISCORD_CONNECTOR"}),
    "dropbox": frozenset({"DROPBOX_FILE"}),
    "gmail": frozenset({"GOOGLE_GMAIL_CONNECTOR"}),
    "google_drive": frozenset({"GOOGLE_DRIVE_FILE"}),
    "jira": frozenset({"JIRA_CONNECTOR"}),
    "linear": frozenset({"LINEAR_CONNECTOR"}),
    "luma": frozenset({"LUMA_CONNECTOR"}),
    "notion": frozenset({"NOTION_CONNECTOR"}),
    "onedrive": frozenset({"ONEDRIVE_FILE"}),
    "slack": frozenset({"SLACK_CONNECTOR"}),
    "teams": frozenset({"TEAMS_CONNECTOR"}),
}
