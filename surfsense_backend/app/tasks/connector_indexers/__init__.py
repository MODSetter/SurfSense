"""
Connector indexers module for background tasks.

Each indexer handles content indexing from a specific connector type.
Live connectors (Slack, Linear, Jira, ClickUp, Airtable, Discord, Teams,
Luma) now use real-time agent tools instead of background indexing.
"""

from .bookstack_indexer import index_bookstack_pages
from .confluence_indexer import index_confluence_pages
from .elasticsearch_indexer import index_elasticsearch_documents
from .github_indexer import index_github_repos
from .google_calendar_indexer import index_google_calendar_events
from .google_drive_indexer import index_google_drive_files
from .google_gmail_indexer import index_google_gmail_messages
from .notion_indexer import index_notion_pages
from .obsidian_indexer import index_obsidian_vault
from .webcrawler_indexer import index_crawled_urls

__all__ = [
    "index_bookstack_pages",
    "index_confluence_pages",
    "index_elasticsearch_documents",
    "index_github_repos",
    "index_google_calendar_events",
    "index_google_drive_files",
    "index_google_gmail_messages",
    "index_notion_pages",
    "index_obsidian_vault",
    "index_crawled_urls",
]
