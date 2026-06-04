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

from app.agents.shared.middleware.dedup_tool_calls import (
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
from .teams import (
    create_list_teams_channels_tool,
    create_read_teams_messages_tool,
    create_send_teams_message_tool,
)
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
# Deferred-import factories
# =============================================================================
# Used for tools whose impls live under ``multi_agent_chat``. Importing those
# at module-load time would cycle (``multi_agent_chat`` middleware imports
# this registry). The import inside the factory runs only when
# ``build_tools`` is called, by which point ``multi_agent_chat`` is fully
# initialised.


def _build_create_automation_tool(deps: dict[str, Any]) -> BaseTool:
    from app.agents.multi_agent_chat.main_agent.tools.automation import (
        create_create_automation_tool,
    )

    return create_create_automation_tool(
        search_space_id=deps["search_space_id"],
        user_id=deps["user_id"],
        llm=deps["llm"],
    )


def _build_scrape_webpage_tool(deps: dict[str, Any]) -> BaseTool:
    # ``scrape_webpage`` is owned by the main agent (its sole live consumer);
    # deferred import keeps this catalog free of a ``multi_agent_chat`` cycle.
    from app.agents.multi_agent_chat.main_agent.tools.scrape_webpage import (
        create_scrape_webpage_tool,
    )

    return create_scrape_webpage_tool(firecrawl_api_key=deps.get("firecrawl_api_key"))


def _build_update_memory_tool(deps: dict[str, Any]) -> BaseTool:
    # ``update_memory`` is owned by the main agent; deferred import (see above).
    from app.agents.multi_agent_chat.main_agent.tools.update_memory import (
        create_update_memory_tool,
        create_update_team_memory_tool,
    )

    if deps["thread_visibility"] == ChatVisibility.SEARCH_SPACE:
        return create_update_team_memory_tool(
            search_space_id=deps["search_space_id"],
            db_session=deps["db_session"],
            llm=deps.get("llm"),
        )
    return create_update_memory_tool(
        user_id=deps["user_id"],
        db_session=deps["db_session"],
        llm=deps.get("llm"),
    )


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
        factory=_build_scrape_webpage_tool,
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
    # AUTOMATION AUTHORING - single HITL tool. The tool takes an NL ``intent``
    # from the main agent, drafts the full AutomationCreate JSON via a focused
    # sub-LLM, surfaces it on an approval card, and persists on approval. The
    # factory defers its import because the impl lives under ``multi_agent_chat``
    # and that package transitively pulls this registry via middleware;
    # deferring to ``build_tools`` call-time breaks the cycle without a
    # parallel registry.
    # =========================================================================
    ToolDefinition(
        name="create_automation",
        description="Draft an automation from an NL intent; user approves the card; tool saves",
        factory=_build_create_automation_tool,
        requires=["search_space_id", "user_id", "llm"],
    ),
    # =========================================================================
    # MEMORY TOOL - single update_memory, private or team by thread_visibility
    # =========================================================================
    ToolDefinition(
        name="update_memory",
        description="Save important long-term facts, preferences, and instructions to the (personal or team) memory",
        factory=_build_update_memory_tool,
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
    # Auto-disabled when no Notion connector is configured    # =========================================================================
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
    # Auto-disabled when no Google Drive connector is configured    # =========================================================================
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
    # Auto-disabled when no Dropbox connector is configured    # =========================================================================
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
    # Auto-disabled when no OneDrive connector is configured    # =========================================================================
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
    # Auto-disabled when no Confluence connector is configured    # =========================================================================
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
