"""Connector-type to subagent name; subagent name to availability tokens for build_subagents."""

from __future__ import annotations

# Connected apps (hosted MCP + interim-native Gmail/Calendar) all route to the
# single ``mcp_discovery`` subagent. File connectors stay native (they enrich
# the knowledge base). Deprecated connectors (Discord/Teams/Luma) are omitted:
# they have no agent subagent, so their rows produce no tools.
CONNECTOR_TYPE_TO_CONNECTOR_AGENT_MAPS: dict[str, str] = {
    "GOOGLE_GMAIL_CONNECTOR": "mcp_discovery",
    "COMPOSIO_GMAIL_CONNECTOR": "mcp_discovery",
    "GOOGLE_CALENDAR_CONNECTOR": "mcp_discovery",
    "COMPOSIO_GOOGLE_CALENDAR_CONNECTOR": "mcp_discovery",
    "LINEAR_CONNECTOR": "mcp_discovery",
    "JIRA_CONNECTOR": "mcp_discovery",
    "CLICKUP_CONNECTOR": "mcp_discovery",
    "SLACK_CONNECTOR": "mcp_discovery",
    "AIRTABLE_CONNECTOR": "mcp_discovery",
    "NOTION_CONNECTOR": "mcp_discovery",
    "CONFLUENCE_CONNECTOR": "mcp_discovery",
    "MCP_CONNECTOR": "mcp_discovery",
    "GOOGLE_DRIVE_CONNECTOR": "google_drive",
    "COMPOSIO_GOOGLE_DRIVE_CONNECTOR": "google_drive",
    "DROPBOX_CONNECTOR": "dropbox",
    "ONEDRIVE_CONNECTOR": "onedrive",
}

# ``mcp_discovery`` is gated any-of: present iff the workspace has at least one
# connected app. Tokens are searchable-type strings (Composio Gmail/Calendar
# map to the GOOGLE_* tokens in connector_searchable_types).
SUBAGENT_TO_REQUIRED_CONNECTOR_MAP: dict[str, frozenset[str]] = {
    "amazon": frozenset(),
    "deliverables": frozenset(),
    "knowledge_base": frozenset(),
    "web_crawler": frozenset(),
    "youtube": frozenset(),
    "google_maps": frozenset(),
    "google_search": frozenset(),
    "reddit": frozenset(),
    "instagram": frozenset(),
    "tiktok": frozenset(),
    "walmart": frozenset(),
    "mcp_discovery": frozenset(
        {
            "SLACK_CONNECTOR",
            "JIRA_CONNECTOR",
            "LINEAR_CONNECTOR",
            "CLICKUP_CONNECTOR",
            "AIRTABLE_CONNECTOR",
            "NOTION_CONNECTOR",
            "CONFLUENCE_CONNECTOR",
            "GOOGLE_GMAIL_CONNECTOR",
            "GOOGLE_CALENDAR_CONNECTOR",
            "MCP_CONNECTOR",
        }
    ),
    "dropbox": frozenset({"DROPBOX_FILE"}),
    "google_drive": frozenset({"GOOGLE_DRIVE_FILE"}),
    "onedrive": frozenset({"ONEDRIVE_FILE"}),
}

# Old per-connector subagent names, kept working for checkpoint resume: a
# ``task(subagent_type="gmail")`` paused before the MCP consolidation resolves
# to the consolidated ``mcp_discovery`` subagent instead of hard-failing
# "subagent does not exist". New routing never emits these names.
LEGACY_SUBAGENT_ALIASES: dict[str, str] = {
    "gmail": "mcp_discovery",
    "calendar": "mcp_discovery",
    "linear": "mcp_discovery",
    "jira": "mcp_discovery",
    "clickup": "mcp_discovery",
    "slack": "mcp_discovery",
    "airtable": "mcp_discovery",
    "notion": "mcp_discovery",
    "confluence": "mcp_discovery",
    "discord": "mcp_discovery",
    "teams": "mcp_discovery",
    "luma": "mcp_discovery",
}
