"""Backward-compatible shim package.

The agent tools now live in the shared kernel at ``app.agents.shared.tools``.
This package re-exports the public surface (and keeps ``invalid_tool`` /
``registry`` submodule shims) so the frozen single-agent stack
(``new_chat.__init__`` and ``chat_deepagent``) keeps working until that stack is
retired. All live code imports from ``app.agents.shared.tools`` directly.
"""

from app.agents.shared.tools import (
    BUILTIN_TOOLS,
    CONNECTOR_DESCRIPTIONS,
    ToolDefinition,
    build_tools,
    create_generate_image_tool,
    create_generate_podcast_tool,
    create_generate_video_presentation_tool,
    create_scrape_webpage_tool,
    create_update_memory_tool,
    create_update_team_memory_tool,
    format_documents_for_context,
    get_all_tool_names,
    get_default_enabled_tools,
    get_tool_by_name,
    search_knowledge_base_async,
)

__all__ = [
    "BUILTIN_TOOLS",
    "CONNECTOR_DESCRIPTIONS",
    "ToolDefinition",
    "build_tools",
    "create_generate_image_tool",
    "create_generate_podcast_tool",
    "create_generate_video_presentation_tool",
    "create_scrape_webpage_tool",
    "create_update_memory_tool",
    "create_update_team_memory_tool",
    "format_documents_for_context",
    "get_all_tool_names",
    "get_default_enabled_tools",
    "get_tool_by_name",
    "search_knowledge_base_async",
]
