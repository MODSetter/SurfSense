"""Pure-data catalog of built-in agent tools.

This module advertises *what* tools exist and their display metadata. It is
intentionally free of any tool implementation imports (no connectors, no
factories) so it can be consumed without pulling the whole tool dependency
graph — and so connector packages stay independently deletable.

The single live consumer is the ``GET /agent/tools`` endpoint, which renders
the tool picker in the web UI. Tool *construction* lives elsewhere:

* main-agent tools  -> ``app.agents.chat.multi_agent_chat.main_agent.tools.registry``
* subagent / connector tools -> ``app.agents.chat.multi_agent_chat.subagents.*``
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolMetadata:
    """Display metadata for a single built-in tool.

    Attributes:
        name: Unique identifier for the tool.
        description: Human-readable description of what the tool does.
        enabled_by_default: Whether the tool is on when no explicit config
            is provided.
        hidden: WIP tools that should be excluded from public listings.

    """

    name: str
    description: str
    enabled_by_default: bool = True
    hidden: bool = False


# Catalog of all built-in tools. Contributors: add new tools here so they show
# up in the UI tool picker. This list carries metadata only — wire the actual
# implementation in the relevant builder/registry module.
TOOL_CATALOG: list[ToolMetadata] = [
    ToolMetadata(
        name="generate_podcast",
        description="Generate an audio podcast from provided content",
    ),
    ToolMetadata(
        name="generate_video_presentation",
        description="Generate a video presentation with slides and narration from provided content",
    ),
    ToolMetadata(
        name="generate_report",
        description="Generate a structured report from provided content and export it",
    ),
    ToolMetadata(
        name="generate_resume",
        description="Generate a professional resume as a Typst document",
    ),
    ToolMetadata(
        name="generate_image",
        description="Generate images from text descriptions using AI image models",
    ),
    ToolMetadata(
        name="search_knowledge_base",
        description="Search the user's knowledge base with hybrid semantic + keyword retrieval",
    ),
    ToolMetadata(
        name="scrape_webpage",
        description="Scrape and extract the main content from a webpage",
    ),
    ToolMetadata(
        name="create_automation",
        description="Draft an automation from an NL intent; user approves the card; tool saves",
    ),
    ToolMetadata(
        name="update_memory",
        description="Save important long-term facts, preferences, and instructions to the (personal or team) memory",
    ),
    ToolMetadata(
        name="create_notion_page",
        description="Create a new page in the user's Notion workspace",
    ),
    ToolMetadata(
        name="update_notion_page",
        description="Append new content to an existing Notion page",
    ),
    ToolMetadata(
        name="delete_notion_page", description="Delete an existing Notion page"
    ),
    ToolMetadata(
        name="create_google_drive_file",
        description="Create a new Google Doc or Google Sheet in Google Drive",
    ),
    ToolMetadata(
        name="delete_google_drive_file",
        description="Move an indexed Google Drive file to trash",
    ),
    ToolMetadata(
        name="create_dropbox_file", description="Create a new file in Dropbox"
    ),
    ToolMetadata(name="delete_dropbox_file", description="Delete a file from Dropbox"),
    ToolMetadata(
        name="create_onedrive_file",
        description="Create a new file in Microsoft OneDrive",
    ),
    ToolMetadata(
        name="delete_onedrive_file",
        description="Move a OneDrive file to the recycle bin",
    ),
    ToolMetadata(
        name="search_calendar_events",
        description="Search Google Calendar events within a date range",
    ),
    ToolMetadata(
        name="create_calendar_event",
        description="Create a new event on Google Calendar",
    ),
    ToolMetadata(
        name="update_calendar_event",
        description="Update an existing indexed Google Calendar event",
    ),
    ToolMetadata(
        name="delete_calendar_event",
        description="Delete an existing indexed Google Calendar event",
    ),
    ToolMetadata(
        name="search_gmail",
        description="Search emails in Gmail using Gmail search syntax",
    ),
    ToolMetadata(
        name="read_gmail_email",
        description="Read the full content of a specific Gmail email",
    ),
    ToolMetadata(
        name="create_gmail_draft", description="Create a draft email in Gmail"
    ),
    ToolMetadata(name="send_gmail_email", description="Send an email via Gmail"),
    ToolMetadata(
        name="trash_gmail_email", description="Move an indexed email to trash in Gmail"
    ),
    ToolMetadata(
        name="update_gmail_draft", description="Update an existing Gmail draft"
    ),
    ToolMetadata(
        name="create_confluence_page",
        description="Create a new page in the user's Confluence space",
    ),
    ToolMetadata(
        name="update_confluence_page",
        description="Update an existing indexed Confluence page",
    ),
    ToolMetadata(
        name="delete_confluence_page",
        description="Delete an existing indexed Confluence page",
    ),
    ToolMetadata(
        name="list_discord_channels",
        description="List text channels in the connected Discord server",
    ),
    ToolMetadata(
        name="read_discord_messages",
        description="Read recent messages from a Discord text channel",
    ),
    ToolMetadata(
        name="send_discord_message",
        description="Send a message to a Discord text channel",
    ),
    ToolMetadata(
        name="list_teams_channels",
        description="List Microsoft Teams and their channels",
    ),
    ToolMetadata(
        name="read_teams_messages",
        description="Read recent messages from a Microsoft Teams channel",
    ),
    ToolMetadata(
        name="send_teams_message",
        description="Send a message to a Microsoft Teams channel",
    ),
    ToolMetadata(
        name="list_luma_events", description="List upcoming and recent Luma events"
    ),
    ToolMetadata(
        name="read_luma_event",
        description="Read detailed information about a specific Luma event",
    ),
    ToolMetadata(name="create_luma_event", description="Create a new event on Luma"),
]
