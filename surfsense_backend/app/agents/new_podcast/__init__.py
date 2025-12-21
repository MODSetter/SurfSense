"""
SurfSense New Podcast module.

This module provides the podcast deep agent implementation using the deepagents
library, enabling conversational podcast generation with knowledge base integration.

Main exports:
- create_surfsense_podcast_agent: Factory function to create a podcast agent
- PodcastContextSchema: TypedDict for agent context
- build_podcast_system_prompt: Function to build the system prompt
- Tool factories for podcast generation
"""

from .context import PodcastContextSchema
from .podcast_deepagent import create_surfsense_podcast_agent
from .podcast_tools import (
    PodcastTranscriptEntry,
    PodcastTranscripts,
    create_generate_podcast_audio_tool,
    create_generate_podcast_transcript_tool,
)
from .system_prompt import PODCAST_SYSTEM_PROMPT, build_podcast_system_prompt

__all__ = [
    # Main agent factory
    "create_surfsense_podcast_agent",
    # Context schema
    "PodcastContextSchema",
    # System prompt
    "PODCAST_SYSTEM_PROMPT",
    "build_podcast_system_prompt",
    # Tool factories
    "create_generate_podcast_audio_tool",
    "create_generate_podcast_transcript_tool",
    # Pydantic models
    "PodcastTranscriptEntry",
    "PodcastTranscripts",
]

