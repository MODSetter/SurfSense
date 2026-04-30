"""Registry tool names grouped by multi-agent routing category.

Each string must match ``ToolDefinition.name`` in
``app.agents.new_chat.tools.registry.BUILTIN_TOOLS`` — these are **not** guessed or MCP-only:
:class:`~app.agents.multi_agent_chat.core.registry.subset.build_registry_tools_for_category`
uses synchronous :func:`~app.agents.new_chat.tools.registry.build_tools`, which only instantiates
``BUILTIN_TOOLS``. MCP tools are loaded separately and merged in ``supervisor_routing``.

Connectors that exist for search/indexing but have **no** entry in ``BUILTIN_TOOLS`` correctly have
no row here (no chat tools to delegate)."""

from __future__ import annotations

# Keys match supervisor routing tool names; values match ``BUILTIN_TOOLS`` names exactly.
TOOL_NAMES_BY_CATEGORY: dict[str, list[str]] = {
    "gmail": [
        "search_gmail",
        "read_gmail_email",
        "create_gmail_draft",
        "send_gmail_email",
        "trash_gmail_email",
        "update_gmail_draft",
    ],
    "calendar": [
        "search_calendar_events",
        "create_calendar_event",
        "update_calendar_event",
        "delete_calendar_event",
    ],
    "research": [
        "web_search",
        "scrape_webpage",
        "search_surfsense_docs",
    ],
    "deliverables": [
        "generate_podcast",
        "generate_video_presentation",
        "generate_report",
        "generate_resume",
        "generate_image",
    ],
    "memory": [
        "update_memory",
    ],
    "discord": [
        "list_discord_channels",
        "read_discord_messages",
        "send_discord_message",
    ],
    "teams": [
        "list_teams_channels",
        "read_teams_messages",
        "send_teams_message",
    ],
    "notion": [
        "create_notion_page",
        "update_notion_page",
        "delete_notion_page",
    ],
    "confluence": [
        "create_confluence_page",
        "update_confluence_page",
        "delete_confluence_page",
    ],
    "google_drive": [
        "create_google_drive_file",
        "delete_google_drive_file",
    ],
    "dropbox": [
        "create_dropbox_file",
        "delete_dropbox_file",
    ],
    "onedrive": [
        "create_onedrive_file",
        "delete_onedrive_file",
    ],
    "luma": [
        "list_luma_events",
        "read_luma_event",
        "create_luma_event",
    ],
}

REGISTRY_ROUTING_CATEGORY_KEYS: tuple[str, ...] = tuple(TOOL_NAMES_BY_CATEGORY.keys())
