"""Chat agents module."""

from .chat_deepagent import (
    SURFSENSE_CITATION_INSTRUCTIONS,
    SURFSENSE_SYSTEM_PROMPT,
    SurfSenseContextSchema,
    build_surfsense_system_prompt,
    create_chat_litellm_from_config,
    create_surfsense_deep_agent,
    load_llm_config_from_yaml,
)
from .knowledge_base import (
    create_search_knowledge_base_tool,
    format_documents_for_context,
    search_knowledge_base_async,
)

__all__ = [
    "SURFSENSE_CITATION_INSTRUCTIONS",
    "SURFSENSE_SYSTEM_PROMPT",
    "SurfSenseContextSchema",
    "build_surfsense_system_prompt",
    "create_chat_litellm_from_config",
    "create_search_knowledge_base_tool",
    "create_surfsense_deep_agent",
    "format_documents_for_context",
    "load_llm_config_from_yaml",
    "search_knowledge_base_async",
]
