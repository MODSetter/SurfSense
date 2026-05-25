"""Load an LLM + AgentConfig bundle for a given config id.

Handles both code paths uniformly:
- ``config_id >= 0`` → database-backed ``NewLLMConfig`` row (per-user/per-space).
- ``config_id < 0``  → YAML-defined global LLM config (built-in defaults).

Returns ``(llm, agent_config, error_message)``; on success ``error_message`` is
``None``. The caller emits the friendly SSE error frame.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.llm_config import (
    AgentConfig,
    create_chat_litellm_from_agent_config,
    create_chat_litellm_from_config,
    load_agent_config,
    load_global_llm_config_by_id,
)


async def load_llm_bundle(
    session: AsyncSession,
    *,
    config_id: int,
    search_space_id: int,
) -> tuple[Any, AgentConfig | None, str | None]:
    if config_id >= 0:
        loaded_agent_config = await load_agent_config(
            session=session,
            config_id=config_id,
            search_space_id=search_space_id,
        )
        if not loaded_agent_config:
            return (
                None,
                None,
                f"Failed to load NewLLMConfig with id {config_id}",
            )
        return (
            create_chat_litellm_from_agent_config(loaded_agent_config),
            loaded_agent_config,
            None,
        )

    loaded_llm_config = load_global_llm_config_by_id(config_id)
    if not loaded_llm_config:
        return None, None, f"Failed to load LLM config with id {config_id}"
    return (
        create_chat_litellm_from_config(loaded_llm_config),
        AgentConfig.from_yaml_config(loaded_llm_config),
        None,
    )
