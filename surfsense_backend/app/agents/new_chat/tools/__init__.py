"""
Tools module for SurfSense deep agent.

This module contains all the tools available to the SurfSense agent.
To add a new tool, see the documentation in registry.py.

Available tools:
- search_surfsense_docs: Search Surfsense documentation for usage help
- generate_podcast: Generate audio podcasts from content
- generate_video_presentation: Generate video presentations with slides and narration
- generate_image: Generate images from text descriptions using AI models
- scrape_webpage: Extract content from webpages
- update_memory: Update the user's / team's memory document
- save_memory: Store facts/preferences about the user
- recall_memory: Retrieve relevant user memories
- get_live_token_price: Get real-time crypto price from DexScreener
- get_live_token_data: Get comprehensive real-time crypto market data
"""

# Registry exports
# Tool factory exports (for direct use)
from .crypto_realtime import (
    create_get_live_token_data_tool,
    create_get_live_token_price_tool,
)
from .display_image import create_display_image_tool
from .generate_image import create_generate_image_tool
from .knowledge_base import (
    CONNECTOR_DESCRIPTIONS,
    format_documents_for_context,
    search_knowledge_base_async,
)
from .podcast import create_generate_podcast_tool
from .registry import (
    BUILTIN_TOOLS,
    ToolDefinition,
    build_tools,
    get_all_tool_names,
    get_default_enabled_tools,
    get_tool_by_name,
)
from .scrape_webpage import create_scrape_webpage_tool
from .search_surfsense_docs import create_search_surfsense_docs_tool
from .update_memory import create_update_memory_tool, create_update_team_memory_tool
from .video_presentation import create_generate_video_presentation_tool

__all__ = [
    # Registry
    "BUILTIN_TOOLS",
    # Knowledge base utilities
    "CONNECTOR_DESCRIPTIONS",
    "ToolDefinition",
    "build_tools",
    # Tool factories
    "create_generate_image_tool",
    "create_generate_podcast_tool",
    "create_generate_video_presentation_tool",
    "create_get_live_token_data_tool",
    "create_get_live_token_price_tool",
    "create_link_preview_tool",
    "create_recall_memory_tool",
    "create_save_memory_tool",
    "create_scrape_webpage_tool",
    "create_search_surfsense_docs_tool",
    "create_update_memory_tool",
    "create_update_team_memory_tool",
    "format_documents_for_context",
    "get_all_tool_names",
    "get_default_enabled_tools",
    "get_tool_by_name",
    "search_knowledge_base_async",
]
