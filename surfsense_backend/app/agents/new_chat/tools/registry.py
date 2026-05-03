"""Tools registry for SurfSense deep agent.

This module provides a registry pattern for managing tools in the SurfSense agent.
It makes it easy for OSS contributors to add new tools by:
1. Creating a tool factory function in a new file in this directory
2. Registering the tool in the BUILTIN_TOOLS list below

Example of adding a new tool:
------------------------------
1. Create your tool file (e.g., `tools/my_tool.py`):

    from langchain_core.tools import tool
    from sqlalchemy.ext.asyncio import AsyncSession

    def create_my_tool(search_space_id: int, db_session: AsyncSession):
        @tool
        async def my_tool(param: str) -> dict:
            '''My tool description.'''
            # Your implementation
            return {"result": "success"}
        return my_tool

2. Import and register in this file:

    from .my_tool import create_my_tool

    # Add to BUILTIN_TOOLS list:
    ToolDefinition(
        name="my_tool",
        description="Description of what your tool does",
        factory=lambda deps: create_my_tool(
            search_space_id=deps["search_space_id"],
            db_session=deps["db_session"],
        ),
        requires=["search_space_id", "db_session"],
    ),
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from langchain_core.tools import BaseTool

from app.agents.new_chat.middleware.dedup_tool_calls import (
    wrap_dedup_key_by_arg_name,
)
from app.db import ChatVisibility

from .confluence import (
    create_create_confluence_page_tool,
    create_delete_confluence_page_tool,
    create_update_confluence_page_tool,
)
from .connected_accounts import create_get_connected_accounts_tool
from .discord import (
    create_list_discord_channels_tool,
    create_read_discord_messages_tool,
    create_send_discord_message_tool,
)
from .dropbox import (
    create_create_dropbox_file_tool,
    create_delete_dropbox_file_tool,
)
from .generate_image import create_generate_image_tool
from .gmail import (
    create_create_gmail_draft_tool,
    create_read_gmail_email_tool,
    create_search_gmail_tool,
    create_send_gmail_email_tool,
    create_trash_gmail_email_tool,
    create_update_gmail_draft_tool,
)
from .google_calendar import (
    create_create_calendar_event_tool,
    create_delete_calendar_event_tool,
    create_search_calendar_events_tool,
    create_update_calendar_event_tool,
)
from .google_drive import (
    create_create_google_drive_file_tool,
    create_delete_google_drive_file_tool,
)
from .luma import (
    create_create_luma_event_tool,
    create_list_luma_events_tool,
    create_read_luma_event_tool,
)
from .mcp_tool import load_mcp_tools
from .notion import (
    create_create_notion_page_tool,
    create_delete_notion_page_tool,
    create_update_notion_page_tool,
)
from .onedrive import (
    create_create_onedrive_file_tool,
    create_delete_onedrive_file_tool,
)
from .podcast import create_generate_podcast_tool
from .report import create_generate_report_tool
from .resume import create_generate_resume_tool
from .scrape_webpage import create_scrape_webpage_tool
from .search_surfsense_docs import create_search_surfsense_docs_tool
from .teams import (
    create_list_teams_channels_tool,
    create_read_teams_messages_tool,
    create_send_teams_message_tool,
)
from .update_memory import create_update_memory_tool, create_update_team_memory_tool
from .video_presentation import create_generate_video_presentation_tool
from .web_search import create_web_search_tool

logger = logging.getLogger(__name__)

# =============================================================================
# Tool Definition
# =============================================================================


@dataclass
class ToolDefinition:
    """Definition of a tool that can be added to the agent.

    Attributes:
        name: Unique identifier for the tool
        description: Human-readable description of what the tool does
        factory: Callable that creates the tool. Receives a dict of dependencies.
        requires: List of dependency names this tool needs (e.g., "search_space_id", "db_session")
        enabled_by_default: Whether the tool is enabled when no explicit config is provided
        required_connector: Searchable type string (e.g. ``"LINEAR_CONNECTOR"``)
            that must be in ``available_connectors`` for the tool to be enabled.
        dedup_key: Optional callable that maps a tool's ``args`` dict to a
            string signature used by :class:`DedupHITLToolCallsMiddleware`
            to drop duplicate calls within a single LLM response.
        reverse: Optional callable that, given the tool's ``(args, result)``,
            returns a ``ReverseDescriptor`` describing the inverse tool
            invocation. Consumed by the snapshot/revert pipeline.

    """

    name: str
    description: str
    factory: Callable[[dict[str, Any]], BaseTool]
    requires: list[str] = field(default_factory=list)
    enabled_by_default: bool = True
    hidden: bool = False
    required_connector: str | None = None
    dedup_key: Callable[[dict[str, Any]], str] | None = None
    reverse: Callable[[dict[str, Any], Any], dict[str, Any]] | None = None


# =============================================================================
# Built-in Tools Registry
# =============================================================================

# Registry of all built-in tools
# Contributors: Add your new tools here!
BUILTIN_TOOLS: list[ToolDefinition] = [
    # Podcast generation tool
    ToolDefinition(
        name="generate_podcast",
        description="Generate an audio podcast from provided content",
        factory=lambda deps: create_generate_podcast_tool(
            search_space_id=deps["search_space_id"],
            db_session=deps["db_session"],
            thread_id=deps["thread_id"],
        ),
        requires=["search_space_id", "db_session", "thread_id"],
    ),
    # Video presentation generation tool
    ToolDefinition(
        name="generate_video_presentation",
        description="Generate a video presentation with slides and narration from provided content",
        factory=lambda deps: create_generate_video_presentation_tool(
            search_space_id=deps["search_space_id"],
            db_session=deps["db_session"],
            thread_id=deps["thread_id"],
        ),
        requires=["search_space_id", "db_session", "thread_id"],
    ),
    # Report generation tool (inline, short-lived sessions for DB ops)
    # Supports internal KB search via source_strategy so the agent does not
    # need a separate search step before generating.
    ToolDefinition(
        name="generate_report",
        description="Generate a structured report from provided content and export it",
        factory=lambda deps: create_generate_report_tool(
            search_space_id=deps["search_space_id"],
            thread_id=deps["thread_id"],
            connector_service=deps.get("connector_service"),
            available_connectors=deps.get("available_connectors"),
            available_document_types=deps.get("available_document_types"),
        ),
        requires=["search_space_id", "thread_id"],
        # connector_service, available_connectors, and available_document_types
        # are optional — when missing, source_strategy="kb_search" degrades
        # gracefully to "provided"
    ),
    # Resume generation tool (Typst-based, uses rendercv package)
    ToolDefinition(
        name="generate_resume",
        description="Generate a professional resume as a Typst document",
        factory=lambda deps: create_generate_resume_tool(
            search_space_id=deps["search_space_id"],
            thread_id=deps["thread_id"],
        ),
        requires=["search_space_id", "thread_id"],
    ),
    # Generate image tool - creates images using AI models (DALL-E, GPT Image, etc.)
    ToolDefinition(
        name="generate_image",
        description="Generate images from text descriptions using AI image models",
        factory=lambda deps: create_generate_image_tool(
            search_space_id=deps["search_space_id"],
            db_session=deps["db_session"],
        ),
        requires=["search_space_id", "db_session"],
    ),
    # Web scraping tool - extracts content from webpages
    ToolDefinition(
        name="scrape_webpage",
        description="Scrape and extract the main content from a webpage",
        factory=lambda deps: create_scrape_webpage_tool(
            firecrawl_api_key=deps.get("firecrawl_api_key"),
        ),
        requires=[],  # firecrawl_api_key is optional
    ),
    # Web search tool — real-time web search via SearXNG + user-configured engines
    ToolDefinition(
        name="web_search",
        description="Search the web for real-time information using configured search engines",
        factory=lambda deps: create_web_search_tool(
            search_space_id=deps.get("search_space_id"),
            available_connectors=deps.get("available_connectors"),
        ),
        requires=[],
    ),
    # Surfsense documentation search tool
    ToolDefinition(
        name="search_surfsense_docs",
        description="Search Surfsense documentation for help with using the application",
        factory=lambda deps: create_search_surfsense_docs_tool(
            db_session=deps["db_session"],
        ),
        requires=["db_session"],
    ),
    # =========================================================================
    # SERVICE ACCOUNT DISCOVERY
    # Generic tool for the LLM to discover connected accounts and resolve
    # service-specific identifiers (e.g. Jira cloudId, Slack team, etc.)
    # =========================================================================
    ToolDefinition(
        name="get_connected_accounts",
        description="Discover connected accounts for a service and their metadata",
        factory=lambda deps: create_get_connected_accounts_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
    ),
    # =========================================================================
    # MEMORY TOOL - single update_memory, private or team by thread_visibility
    # =========================================================================
    ToolDefinition(
        name="update_memory",
        description="Save important long-term facts, preferences, and instructions to the (personal or team) memory",
        factory=lambda deps: (
            create_update_team_memory_tool(
                search_space_id=deps["search_space_id"],
                db_session=deps["db_session"],
                llm=deps.get("llm"),
            )
            if deps["thread_visibility"] == ChatVisibility.SEARCH_SPACE
            else create_update_memory_tool(
                user_id=deps["user_id"],
                db_session=deps["db_session"],
                llm=deps.get("llm"),
            )
        ),
        requires=[
            "user_id",
            "search_space_id",
            "db_session",
            "thread_visibility",
            "llm",
        ],
    ),
    # =========================================================================
    # NOTION TOOLS - create, update, delete pages
    # Auto-disabled when no Notion connector is configured (see chat_deepagent.py)
    # =========================================================================
    ToolDefinition(
        name="create_notion_page",
        description="Create a new page in the user's Notion workspace",
        factory=lambda deps: create_create_notion_page_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
        required_connector="NOTION_CONNECTOR",
        dedup_key=wrap_dedup_key_by_arg_name("title"),
    ),
    ToolDefinition(
        name="update_notion_page",
        description="Append new content to an existing Notion page",
        factory=lambda deps: create_update_notion_page_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
        required_connector="NOTION_CONNECTOR",
        dedup_key=wrap_dedup_key_by_arg_name("page_title"),
    ),
    ToolDefinition(
        name="delete_notion_page",
        description="Delete an existing Notion page",
        factory=lambda deps: create_delete_notion_page_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
        required_connector="NOTION_CONNECTOR",
        dedup_key=wrap_dedup_key_by_arg_name("page_title"),
    ),
    # =========================================================================
    # GOOGLE DRIVE TOOLS - create files, delete files
    # Auto-disabled when no Google Drive connector is configured (see chat_deepagent.py)
    # =========================================================================
    ToolDefinition(
        name="create_google_drive_file",
        description="Create a new Google Doc or Google Sheet in Google Drive",
        factory=lambda deps: create_create_google_drive_file_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
        required_connector="GOOGLE_DRIVE_FILE",
        dedup_key=wrap_dedup_key_by_arg_name("file_name"),
    ),
    ToolDefinition(
        name="delete_google_drive_file",
        description="Move an indexed Google Drive file to trash",
        factory=lambda deps: create_delete_google_drive_file_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
        required_connector="GOOGLE_DRIVE_FILE",
        dedup_key=wrap_dedup_key_by_arg_name("file_name"),
    ),
    # =========================================================================
    # DROPBOX TOOLS - create and trash files
    # Auto-disabled when no Dropbox connector is configured (see chat_deepagent.py)
    # =========================================================================
    ToolDefinition(
        name="create_dropbox_file",
        description="Create a new file in Dropbox",
        factory=lambda deps: create_create_dropbox_file_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
        required_connector="DROPBOX_FILE",
        dedup_key=wrap_dedup_key_by_arg_name("file_name"),
    ),
    ToolDefinition(
        name="delete_dropbox_file",
        description="Delete a file from Dropbox",
        factory=lambda deps: create_delete_dropbox_file_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
        required_connector="DROPBOX_FILE",
        dedup_key=wrap_dedup_key_by_arg_name("file_name"),
    ),
    # =========================================================================
    # ONEDRIVE TOOLS - create and trash files
    # Auto-disabled when no OneDrive connector is configured (see chat_deepagent.py)
    # =========================================================================
    ToolDefinition(
        name="create_onedrive_file",
        description="Create a new file in Microsoft OneDrive",
        factory=lambda deps: create_create_onedrive_file_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
        required_connector="ONEDRIVE_FILE",
        dedup_key=wrap_dedup_key_by_arg_name("file_name"),
    ),
    ToolDefinition(
        name="delete_onedrive_file",
        description="Move a OneDrive file to the recycle bin",
        factory=lambda deps: create_delete_onedrive_file_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
        required_connector="ONEDRIVE_FILE",
        dedup_key=wrap_dedup_key_by_arg_name("file_name"),
    ),
    # =========================================================================
    # GOOGLE CALENDAR TOOLS - search, create, update, delete events
    # Auto-disabled when no Google Calendar connector is configured
    # =========================================================================
    ToolDefinition(
        name="search_calendar_events",
        description="Search Google Calendar events within a date range",
        factory=lambda deps: create_search_calendar_events_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
        required_connector="GOOGLE_CALENDAR_CONNECTOR",
    ),
    ToolDefinition(
        name="create_calendar_event",
        description="Create a new event on Google Calendar",
        factory=lambda deps: create_create_calendar_event_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
        required_connector="GOOGLE_CALENDAR_CONNECTOR",
        dedup_key=wrap_dedup_key_by_arg_name("title"),
    ),
    ToolDefinition(
        name="update_calendar_event",
        description="Update an existing indexed Google Calendar event",
        factory=lambda deps: create_update_calendar_event_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
        required_connector="GOOGLE_CALENDAR_CONNECTOR",
        dedup_key=wrap_dedup_key_by_arg_name("event_title_or_id"),
    ),
    ToolDefinition(
        name="delete_calendar_event",
        description="Delete an existing indexed Google Calendar event",
        factory=lambda deps: create_delete_calendar_event_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
        required_connector="GOOGLE_CALENDAR_CONNECTOR",
        dedup_key=wrap_dedup_key_by_arg_name("event_title_or_id"),
    ),
    # =========================================================================
    # GMAIL TOOLS - search, read, create drafts, update drafts, send, trash
    # Auto-disabled when no Gmail connector is configured
    # =========================================================================
    ToolDefinition(
        name="search_gmail",
        description="Search emails in Gmail using Gmail search syntax",
        factory=lambda deps: create_search_gmail_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
        required_connector="GOOGLE_GMAIL_CONNECTOR",
    ),
    ToolDefinition(
        name="read_gmail_email",
        description="Read the full content of a specific Gmail email",
        factory=lambda deps: create_read_gmail_email_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
        required_connector="GOOGLE_GMAIL_CONNECTOR",
    ),
    ToolDefinition(
        name="create_gmail_draft",
        description="Create a draft email in Gmail",
        factory=lambda deps: create_create_gmail_draft_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
        required_connector="GOOGLE_GMAIL_CONNECTOR",
        dedup_key=wrap_dedup_key_by_arg_name("subject"),
    ),
    ToolDefinition(
        name="send_gmail_email",
        description="Send an email via Gmail",
        factory=lambda deps: create_send_gmail_email_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
        required_connector="GOOGLE_GMAIL_CONNECTOR",
        dedup_key=wrap_dedup_key_by_arg_name("subject"),
    ),
    ToolDefinition(
        name="trash_gmail_email",
        description="Move an indexed email to trash in Gmail",
        factory=lambda deps: create_trash_gmail_email_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
        required_connector="GOOGLE_GMAIL_CONNECTOR",
        dedup_key=wrap_dedup_key_by_arg_name("email_subject_or_id"),
    ),
    ToolDefinition(
        name="update_gmail_draft",
        description="Update an existing Gmail draft",
        factory=lambda deps: create_update_gmail_draft_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
        required_connector="GOOGLE_GMAIL_CONNECTOR",
        dedup_key=wrap_dedup_key_by_arg_name("draft_subject_or_id"),
    ),
    # =========================================================================
    # CONFLUENCE TOOLS - create, update, delete pages
    # Auto-disabled when no Confluence connector is configured (see chat_deepagent.py)
    # =========================================================================
    ToolDefinition(
        name="create_confluence_page",
        description="Create a new page in the user's Confluence space",
        factory=lambda deps: create_create_confluence_page_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
        required_connector="CONFLUENCE_CONNECTOR",
        dedup_key=wrap_dedup_key_by_arg_name("title"),
    ),
    ToolDefinition(
        name="update_confluence_page",
        description="Update an existing indexed Confluence page",
        factory=lambda deps: create_update_confluence_page_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
        required_connector="CONFLUENCE_CONNECTOR",
        dedup_key=wrap_dedup_key_by_arg_name("page_title_or_id"),
    ),
    ToolDefinition(
        name="delete_confluence_page",
        description="Delete an existing indexed Confluence page",
        factory=lambda deps: create_delete_confluence_page_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
        required_connector="CONFLUENCE_CONNECTOR",
        dedup_key=wrap_dedup_key_by_arg_name("page_title_or_id"),
    ),
    # =========================================================================
    # DISCORD TOOLS - list channels, read messages, send messages
    # Auto-disabled when no Discord connector is configured
    # =========================================================================
    ToolDefinition(
        name="list_discord_channels",
        description="List text channels in the connected Discord server",
        factory=lambda deps: create_list_discord_channels_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
        required_connector="DISCORD_CONNECTOR",
    ),
    ToolDefinition(
        name="read_discord_messages",
        description="Read recent messages from a Discord text channel",
        factory=lambda deps: create_read_discord_messages_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
        required_connector="DISCORD_CONNECTOR",
    ),
    ToolDefinition(
        name="send_discord_message",
        description="Send a message to a Discord text channel",
        factory=lambda deps: create_send_discord_message_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
        required_connector="DISCORD_CONNECTOR",
    ),
    # =========================================================================
    # TEAMS TOOLS - list channels, read messages, send messages
    # Auto-disabled when no Teams connector is configured
    # =========================================================================
    ToolDefinition(
        name="list_teams_channels",
        description="List Microsoft Teams and their channels",
        factory=lambda deps: create_list_teams_channels_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
        required_connector="TEAMS_CONNECTOR",
    ),
    ToolDefinition(
        name="read_teams_messages",
        description="Read recent messages from a Microsoft Teams channel",
        factory=lambda deps: create_read_teams_messages_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
        required_connector="TEAMS_CONNECTOR",
    ),
    ToolDefinition(
        name="send_teams_message",
        description="Send a message to a Microsoft Teams channel",
        factory=lambda deps: create_send_teams_message_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
        required_connector="TEAMS_CONNECTOR",
    ),
    # =========================================================================
    # LUMA TOOLS - list events, read event details, create events
    # Auto-disabled when no Luma connector is configured
    # =========================================================================
    ToolDefinition(
        name="list_luma_events",
        description="List upcoming and recent Luma events",
        factory=lambda deps: create_list_luma_events_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
        required_connector="LUMA_CONNECTOR",
    ),
    ToolDefinition(
        name="read_luma_event",
        description="Read detailed information about a specific Luma event",
        factory=lambda deps: create_read_luma_event_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
        required_connector="LUMA_CONNECTOR",
    ),
    ToolDefinition(
        name="create_luma_event",
        description="Create a new event on Luma",
        factory=lambda deps: create_create_luma_event_tool(
            db_session=deps["db_session"],
            search_space_id=deps["search_space_id"],
            user_id=deps["user_id"],
        ),
        requires=["db_session", "search_space_id", "user_id"],
        required_connector="LUMA_CONNECTOR",
    ),
]


# =============================================================================
# Registry Functions
# =============================================================================


def get_tool_by_name(name: str) -> ToolDefinition | None:
    """Get a tool definition by its name."""
    for tool_def in BUILTIN_TOOLS:
        if tool_def.name == name:
            return tool_def
    return None


def get_connector_gated_tools(
    available_connectors: list[str] | None,
) -> list[str]:
    """Return tool names to disable"""
    available = set() if available_connectors is None else set(available_connectors)

    disabled: list[str] = []
    for tool_def in BUILTIN_TOOLS:
        if tool_def.required_connector and tool_def.required_connector not in available:
            disabled.append(tool_def.name)
    return disabled


def get_all_tool_names() -> list[str]:
    """Get names of all registered tools."""
    return [tool_def.name for tool_def in BUILTIN_TOOLS]


def get_default_enabled_tools() -> list[str]:
    """Get names of tools that are enabled by default (excludes hidden tools)."""
    return [tool_def.name for tool_def in BUILTIN_TOOLS if tool_def.enabled_by_default]


def build_tools(
    dependencies: dict[str, Any],
    enabled_tools: list[str] | None = None,
    disabled_tools: list[str] | None = None,
    additional_tools: list[BaseTool] | None = None,
) -> list[BaseTool]:
    """Build the list of tools for the agent.

    Args:
        dependencies: Dict containing all possible dependencies:
            - search_space_id: The search space ID
            - db_session: Database session
            - connector_service: Connector service instance
            - firecrawl_api_key: Optional Firecrawl API key
        enabled_tools: Explicit list of tool names to enable. If None, uses defaults.
        disabled_tools: List of tool names to disable (applied after enabled_tools).
        additional_tools: Extra tools to add (e.g., custom tools not in registry).

    Returns:
        List of configured tool instances ready for the agent.

    Example:
        # Use all default tools
        tools = build_tools(deps)

        # Use only specific tools
        tools = build_tools(deps, enabled_tools=["generate_report"])

        # Use defaults but disable podcast
        tools = build_tools(deps, disabled_tools=["generate_podcast"])

        # Add custom tools
        tools = build_tools(deps, additional_tools=[my_custom_tool])

    """
    # Determine which tools to enable
    if enabled_tools is not None:
        tool_names_to_use = set(enabled_tools)
    else:
        tool_names_to_use = set(get_default_enabled_tools())

    # Apply disabled list
    if disabled_tools:
        tool_names_to_use -= set(disabled_tools)

    # Build the tools (skip hidden/WIP tools unconditionally)
    tools: list[BaseTool] = []
    for tool_def in BUILTIN_TOOLS:
        if tool_def.hidden or tool_def.name not in tool_names_to_use:
            continue

        # Check that all required dependencies are provided
        missing_deps = [dep for dep in tool_def.requires if dep not in dependencies]
        if missing_deps:
            msg = f"Tool '{tool_def.name}' requires dependencies: {missing_deps}"
            raise ValueError(
                msg,
            )

        # Create the tool
        tool = tool_def.factory(dependencies)
        # Propagate the registry-level metadata so middleware (e.g.
        # ``DedupHITLToolCallsMiddleware``) and the action-log/revert
        # pipeline can pick the resolvers up via ``tool.metadata`` without
        # re-importing :data:`BUILTIN_TOOLS`.
        if tool_def.dedup_key is not None or tool_def.reverse is not None:
            existing_meta = getattr(tool, "metadata", None) or {}
            merged_meta = dict(existing_meta)
            if tool_def.dedup_key is not None:
                merged_meta.setdefault("dedup_key", tool_def.dedup_key)
            if tool_def.reverse is not None:
                merged_meta.setdefault("reverse", tool_def.reverse)
            try:
                tool.metadata = merged_meta
            except Exception:
                logger.debug(
                    "Tool %s rejected metadata mutation; relying on registry lookup",
                    tool_def.name,
                )
        tools.append(tool)

    # Add any additional custom tools
    if additional_tools:
        tools.extend(additional_tools)

    return tools


async def build_tools_async(
    dependencies: dict[str, Any],
    enabled_tools: list[str] | None = None,
    disabled_tools: list[str] | None = None,
    additional_tools: list[BaseTool] | None = None,
    include_mcp_tools: bool = True,
) -> list[BaseTool]:
    """Async version of build_tools that also loads MCP tools from database.

    Design Note:
    This function exists because MCP tools require database queries to load user configs,
    while built-in tools are created synchronously from static code.

    Alternative: We could make build_tools() itself async and always query the database,
    but that would force async everywhere even when only using built-in tools. The current
    design keeps the simple case (static tools only) synchronous while supporting dynamic
    database-loaded tools through this async wrapper.

    Args:
        dependencies: Dict containing all possible dependencies
        enabled_tools: Explicit list of tool names to enable. If None, uses defaults.
        disabled_tools: List of tool names to disable (applied after enabled_tools).
        additional_tools: Extra tools to add (e.g., custom tools not in registry).
        include_mcp_tools: Whether to load user's MCP tools from database.

    Returns:
        List of configured tool instances ready for the agent, including MCP tools.

    """
    import time

    _perf_log = logging.getLogger("surfsense.perf")
    _perf_log.setLevel(logging.DEBUG)

    _t0 = time.perf_counter()
    tools = build_tools(dependencies, enabled_tools, disabled_tools, additional_tools)
    _perf_log.info(
        "[build_tools_async] Built-in tools in %.3fs (%d tools)",
        time.perf_counter() - _t0,
        len(tools),
    )

    # Load MCP tools if requested and dependencies are available
    if (
        include_mcp_tools
        and "db_session" in dependencies
        and "search_space_id" in dependencies
    ):
        try:
            _t0 = time.perf_counter()
            mcp_tools = await load_mcp_tools(
                dependencies["db_session"],
                dependencies["search_space_id"],
            )
            _perf_log.info(
                "[build_tools_async] MCP tools loaded in %.3fs (%d tools)",
                time.perf_counter() - _t0,
                len(mcp_tools),
            )
            tools.extend(mcp_tools)
            logging.info(
                "Registered %d MCP tools: %s",
                len(mcp_tools),
                [t.name for t in mcp_tools],
            )
        except Exception as e:
            logging.exception("Failed to load MCP tools: %s", e)

    logging.info(
        "Total tools for agent: %d — %s",
        len(tools),
        [t.name for t in tools],
    )

    return tools
