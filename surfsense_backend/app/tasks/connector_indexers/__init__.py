"""
Connector indexers module for background tasks.

This module provides a collection of connector indexers for different platforms
and services. Each indexer is responsible for handling the indexing of content
from a specific connector type.

Available indexers:
- Slack: Index messages from Slack channels
- Notion: Index pages from Notion workspaces
- GitHub: Index repositories and files from GitHub
- Linear: Index issues from Linear workspaces
- Jira: Index issues from Jira projects
- Confluence: Index pages from Confluence spaces
- Discord: Index messages from Discord servers
- ClickUp: Index tasks from ClickUp workspaces
- Google Calendar: Index events from Google Calendar
"""

# Communication platforms
from .clickup_indexer import index_clickup_tasks
from .confluence_indexer import index_confluence_pages
from .discord_indexer import index_discord_messages

# Development platforms
from .github_indexer import index_github_repos

# Calendar and scheduling
from .google_calendar_indexer import index_google_calendar_events
from .jira_indexer import index_jira_issues

# Issue tracking and project management
from .linear_indexer import index_linear_issues

# Documentation and knowledge management
from .notion_indexer import index_notion_pages
from .slack_indexer import index_slack_messages

__all__ = [
    "index_clickup_tasks",
    "index_confluence_pages",
    "index_discord_messages",
    # Development platforms
    "index_github_repos",
    # Calendar and scheduling
    "index_google_calendar_events",
    "index_jira_issues",
    # Issue tracking and project management
    "index_linear_issues",
    # Documentation and knowledge management
    "index_notion_pages",
    # Communication platforms
    "index_slack_messages",
]
