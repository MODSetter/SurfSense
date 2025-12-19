"""Chat agents module."""

from .chat_deepagent import create_surfsense_deep_agent
from .context import SurfSenseContextSchema
from .knowledge_base import (
    create_search_knowledge_base_tool,
    format_documents_for_context,
    search_knowledge_base_async,
)
from .llm_config import create_chat_litellm_from_config, load_llm_config_from_yaml
from .system_prompt import (
    SURFSENSE_CITATION_INSTRUCTIONS,
    SURFSENSE_SYSTEM_PROMPT,
    build_surfsense_system_prompt,
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
