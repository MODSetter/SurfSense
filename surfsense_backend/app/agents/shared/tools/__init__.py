"""
Tools module for SurfSense deep agent.

This module contains all the tools available to the SurfSense agent.
To add a new tool, see the documentation in registry.py.

Available tools:
- generate_podcast: Generate audio podcasts from content
- generate_video_presentation: Generate video presentations with slides and narration
- generate_image: Generate images from text descriptions using AI models
"""

# Registry exports
# Tool factory exports (for direct use)
from .generate_image import create_generate_image_tool
from .knowledge_base import (
    CONNECTOR_DESCRIPTIONS,
    format_documents_for_context,
    search_knowledge_base_async,
)
from .catalog import TOOL_CATALOG, ToolMetadata
from .podcast import create_generate_podcast_tool
from .video_presentation import create_generate_video_presentation_tool

__all__ = [
    # Tool catalog (display metadata)
    "TOOL_CATALOG",
    # Knowledge base utilities
    "CONNECTOR_DESCRIPTIONS",
    "ToolMetadata",
    # Tool factories
    "create_generate_image_tool",
    "create_generate_podcast_tool",
    "create_generate_video_presentation_tool",
    "format_documents_for_context",
    "search_knowledge_base_async",
]
