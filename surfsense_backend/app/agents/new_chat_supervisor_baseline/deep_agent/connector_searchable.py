"""Map connector enum values to searchable document/connector type strings."""

from __future__ import annotations

from typing import Any

_CONNECTOR_TYPE_TO_SEARCHABLE: dict[str, str] = {
    "TAVILY_API": "TAVILY_API",
    "LINKUP_API": "LINKUP_API",
    "BAIDU_SEARCH_API": "BAIDU_SEARCH_API",
    "SLACK_CONNECTOR": "SLACK_CONNECTOR",
    "TEAMS_CONNECTOR": "TEAMS_CONNECTOR",
    "NOTION_CONNECTOR": "NOTION_CONNECTOR",
    "GITHUB_CONNECTOR": "GITHUB_CONNECTOR",
    "LINEAR_CONNECTOR": "LINEAR_CONNECTOR",
    "DISCORD_CONNECTOR": "DISCORD_CONNECTOR",
    "JIRA_CONNECTOR": "JIRA_CONNECTOR",
    "CONFLUENCE_CONNECTOR": "CONFLUENCE_CONNECTOR",
    "CLICKUP_CONNECTOR": "CLICKUP_CONNECTOR",
    "GOOGLE_CALENDAR_CONNECTOR": "GOOGLE_CALENDAR_CONNECTOR",
    "GOOGLE_GMAIL_CONNECTOR": "GOOGLE_GMAIL_CONNECTOR",
    "GOOGLE_DRIVE_CONNECTOR": "GOOGLE_DRIVE_FILE",
    "AIRTABLE_CONNECTOR": "AIRTABLE_CONNECTOR",
    "LUMA_CONNECTOR": "LUMA_CONNECTOR",
    "ELASTICSEARCH_CONNECTOR": "ELASTICSEARCH_CONNECTOR",
    "WEBCRAWLER_CONNECTOR": "CRAWLED_URL",
    "BOOKSTACK_CONNECTOR": "BOOKSTACK_CONNECTOR",
    "CIRCLEBACK_CONNECTOR": "CIRCLEBACK",
    "OBSIDIAN_CONNECTOR": "OBSIDIAN_CONNECTOR",
    "DROPBOX_CONNECTOR": "DROPBOX_FILE",
    "ONEDRIVE_CONNECTOR": "ONEDRIVE_FILE",
    "COMPOSIO_GOOGLE_DRIVE_CONNECTOR": "GOOGLE_DRIVE_FILE",
    "COMPOSIO_GMAIL_CONNECTOR": "GOOGLE_GMAIL_CONNECTOR",
    "COMPOSIO_GOOGLE_CALENDAR_CONNECTOR": "GOOGLE_CALENDAR_CONNECTOR",
}

_ALWAYS_AVAILABLE_DOC_TYPES: tuple[str, ...] = (
    "EXTENSION",
    "FILE",
    "NOTE",
    "YOUTUBE_VIDEO",
)


def map_connectors_to_searchable_types(connector_types: list[Any]) -> list[str]:
    """Map connector types to searchable strings; dedupe preserving order."""
    result_set: set[str] = set()
    result_list: list[str] = []

    for doc_type in _ALWAYS_AVAILABLE_DOC_TYPES:
        if doc_type not in result_set:
            result_set.add(doc_type)
            result_list.append(doc_type)

    for ct in connector_types:
        ct_str = ct.value if hasattr(ct, "value") else str(ct)
        searchable = _CONNECTOR_TYPE_TO_SEARCHABLE.get(ct_str)
        if searchable and searchable not in result_set:
            result_set.add(searchable)
            result_list.append(searchable)

    return result_list
