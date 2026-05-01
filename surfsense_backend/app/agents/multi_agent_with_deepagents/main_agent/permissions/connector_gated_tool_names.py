"""Tool name → required searchable connector type (keep in sync with new_chat ``BUILTIN_TOOLS``)."""

from __future__ import annotations

# Synced from ``app.agents.new_chat.tools.registry`` ToolDefinition.required_connector entries.
_CONNECTOR_GATED: tuple[tuple[str, str], ...] = (
    ("create_notion_page", "NOTION_CONNECTOR"),
    ("update_notion_page", "NOTION_CONNECTOR"),
    ("delete_notion_page", "NOTION_CONNECTOR"),
    ("create_google_drive_file", "GOOGLE_DRIVE_FILE"),
    ("delete_google_drive_file", "GOOGLE_DRIVE_FILE"),
    ("create_dropbox_file", "DROPBOX_FILE"),
    ("delete_dropbox_file", "DROPBOX_FILE"),
    ("create_onedrive_file", "ONEDRIVE_FILE"),
    ("delete_onedrive_file", "ONEDRIVE_FILE"),
    ("search_calendar_events", "GOOGLE_CALENDAR_CONNECTOR"),
    ("create_calendar_event", "GOOGLE_CALENDAR_CONNECTOR"),
    ("update_calendar_event", "GOOGLE_CALENDAR_CONNECTOR"),
    ("delete_calendar_event", "GOOGLE_CALENDAR_CONNECTOR"),
    ("search_gmail", "GOOGLE_GMAIL_CONNECTOR"),
    ("read_gmail_email", "GOOGLE_GMAIL_CONNECTOR"),
    ("create_gmail_draft", "GOOGLE_GMAIL_CONNECTOR"),
    ("send_gmail_email", "GOOGLE_GMAIL_CONNECTOR"),
    ("trash_gmail_email", "GOOGLE_GMAIL_CONNECTOR"),
    ("update_gmail_draft", "GOOGLE_GMAIL_CONNECTOR"),
    ("create_confluence_page", "CONFLUENCE_CONNECTOR"),
    ("update_confluence_page", "CONFLUENCE_CONNECTOR"),
    ("delete_confluence_page", "CONFLUENCE_CONNECTOR"),
    ("list_discord_channels", "DISCORD_CONNECTOR"),
    ("read_discord_messages", "DISCORD_CONNECTOR"),
    ("send_discord_message", "DISCORD_CONNECTOR"),
    ("list_teams_channels", "TEAMS_CONNECTOR"),
    ("read_teams_messages", "TEAMS_CONNECTOR"),
    ("send_teams_message", "TEAMS_CONNECTOR"),
    ("list_luma_events", "LUMA_CONNECTOR"),
    ("read_luma_event", "LUMA_CONNECTOR"),
    ("create_luma_event", "LUMA_CONNECTOR"),
)


def iter_connector_gated_tools() -> tuple[tuple[str, str], ...]:
    return _CONNECTOR_GATED
