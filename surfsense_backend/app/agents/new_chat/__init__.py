"""
SurfSense New Chat Agent Module.

This module provides the SurfSense deep agent with configurable tools,
middleware, and preloaded knowledge-base filesystem behavior.

Directory Structure:
- tools/: All agent tools (podcast, generate_image, web, memory, etc.)
- middleware/: Custom middleware (knowledge search, filesystem, dedup, etc.)
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

# Middleware
from .middleware import (
    DedupHITLToolCallsMiddleware,
    KnowledgeBaseSearchMiddleware,
    SurfSenseFilesystemMiddleware,
)

# System prompt
from .system_prompt import (
    SURFSENSE_CITATION_INSTRUCTIONS,
    SURFSENSE_SYSTEM_PROMPT,
    build_surfsense_system_prompt,
)

# Tools - registry exports
# Tools - factory exports (for direct use)
# Tools - knowledge base utilities
from .tools import (
    BUILTIN_TOOLS,
    ToolDefinition,
    build_tools,
    create_generate_podcast_tool,
    create_scrape_webpage_tool,
    format_documents_for_context,
    get_all_tool_names,
    get_default_enabled_tools,
    get_tool_by_name,
    search_knowledge_base_async,
)

__all__ = [
    # Tools registry
    "BUILTIN_TOOLS",
    # System prompt
    "SURFSENSE_CITATION_INSTRUCTIONS",
    "SURFSENSE_SYSTEM_PROMPT",
    # Middleware
    "DedupHITLToolCallsMiddleware",
    "KnowledgeBaseSearchMiddleware",
    # Context
    "SurfSenseContextSchema",
    "SurfSenseFilesystemMiddleware",
    "ToolDefinition",
    "build_surfsense_system_prompt",
    "build_tools",
    # LLM config
    "create_chat_litellm_from_config",
    # Tool factories
    "create_generate_podcast_tool",
    "create_scrape_webpage_tool",
    # Agent factory
    "create_surfsense_deep_agent",
    # Knowledge base utilities
    "format_documents_for_context",
    "get_all_tool_names",
    "get_default_enabled_tools",
    "get_tool_by_name",
    "load_llm_config_from_yaml",
    "search_knowledge_base_async",
]
