from __future__ import annotations

SHARED_CONNECTOR_TOOLS: frozenset[str] = frozenset(
    {
        "create_calendar_event",
        "create_confluence_page",
        "create_dropbox_file",
        "create_gmail_draft",
        "create_google_drive_file",
        "create_jira_issue",
        "create_linear_issue",
        "create_notion_page",
        "create_onedrive_file",
        "delete_calendar_event",
        "delete_confluence_page",
        "delete_dropbox_file",
        "delete_google_drive_file",
        "delete_jira_issue",
        "delete_linear_issue",
        "delete_notion_page",
        "delete_onedrive_file",
        "send_gmail_email",
        "trash_gmail_email",
        "update_calendar_event",
        "update_confluence_page",
        "update_gmail_draft",
        "update_jira_issue",
        "update_linear_issue",
        "update_notion_page",
    }
)
