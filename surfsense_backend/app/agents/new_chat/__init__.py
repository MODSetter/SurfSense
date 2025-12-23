"""
SurfSense New Chat Agent Module.

This module provides the SurfSense deep agent with configurable tools
for knowledge base search, podcast generation, and more.

Directory Structure:
- tools/: All agent tools (knowledge_base, podcast, link_preview, etc.)
- chat_deepagent.py: Main agent factory
- system_prompt.py: System prompts and instructions
- context.py: Context schema for the agent
- checkpointer.py: LangGraph checkpointer setup
- llm_config.py: LLM configuration utilities
- utils.py: Shared utilities
"""

# Agent factory
from .chat_deepagent import create_surfsense_deep_agent

# Context
from .context import SurfSenseContextSchema

# LLM config
from .llm_config import create_chat_litellm_from_config, load_llm_config_from_yaml

# System prompt
from .system_prompt import (
    SURFSENSE_CITATION_INSTRUCTIONS,
    SURFSENSE_SYSTEM_PROMPT,
    build_surfsense_system_prompt,
)

# Tools - registry exports
from .tools import (
    BUILTIN_TOOLS,
    ToolDefinition,
    build_tools,
    get_all_tool_names,
    get_default_enabled_tools,
    get_tool_by_name,
)

# Tools - factory exports (for direct use)
from .tools import (
    create_display_image_tool,
    create_generate_podcast_tool,
    create_link_preview_tool,
    create_scrape_webpage_tool,
    create_search_knowledge_base_tool,
)

# Tools - knowledge base utilities
from .tools import (
    format_documents_for_context,
    search_knowledge_base_async,
)

__all__ = [
    # Agent factory
    "create_surfsense_deep_agent",
    # Context
    "SurfSenseContextSchema",
    # LLM config
    "create_chat_litellm_from_config",
    "load_llm_config_from_yaml",
    # System prompt
    "SURFSENSE_CITATION_INSTRUCTIONS",
    "SURFSENSE_SYSTEM_PROMPT",
    "build_surfsense_system_prompt",
    # Tools registry
    "BUILTIN_TOOLS",
    "ToolDefinition",
    "build_tools",
    "get_all_tool_names",
    "get_default_enabled_tools",
    "get_tool_by_name",
    # Tool factories
    "create_display_image_tool",
    "create_generate_podcast_tool",
    "create_link_preview_tool",
    "create_scrape_webpage_tool",
    "create_search_knowledge_base_tool",
    # Knowledge base utilities
    "format_documents_for_context",
    "search_knowledge_base_async",
]
