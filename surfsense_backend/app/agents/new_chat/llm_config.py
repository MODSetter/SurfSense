"""Backward-compatible shim.

The LLM configuration layer now lives in the shared agent kernel at
``app.agents.shared.llm_config``. This module re-exports it so frozen
single-agent code (``chat_deepagent``) keeps working until that stack is
retired.
"""

from __future__ import annotations

from app.agents.shared.llm_config import (
    AgentConfig,
    SanitizedChatLiteLLM,
    create_chat_litellm_from_agent_config,
    create_chat_litellm_from_config,
    load_agent_config,
    load_agent_llm_config_for_search_space,
    load_global_llm_config_by_id,
    load_llm_config_from_yaml,
    load_new_llm_config_from_db,
)

__all__ = [
    "AgentConfig",
    "SanitizedChatLiteLLM",
    "create_chat_litellm_from_agent_config",
    "create_chat_litellm_from_config",
    "load_agent_config",
    "load_agent_llm_config_for_search_space",
    "load_global_llm_config_by_id",
    "load_llm_config_from_yaml",
    "load_new_llm_config_from_db",
]
