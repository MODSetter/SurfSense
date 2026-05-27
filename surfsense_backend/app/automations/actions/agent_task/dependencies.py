"""Build the per-invocation dependencies the multi_agent_chat factory needs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.tasks.chat.streaming.flows.shared.llm_bundle import load_llm_bundle
from app.tasks.chat.streaming.flows.shared.pre_stream_setup import (
    get_chat_checkpointer,
    setup_connector_and_firecrawl,
)


class DependencyError(Exception):
    """An external dependency (LLM config, checkpointer, ...) refused to load."""


@dataclass(frozen=True, slots=True)
class AgentDependencies:
    """Everything ``create_multi_agent_chat_deep_agent`` needs from the environment."""

    llm: Any
    agent_config: Any
    connector_service: Any
    firecrawl_api_key: str | None
    checkpointer: Any


async def build_dependencies(
    *,
    session: AsyncSession,
    search_space_id: int,
) -> AgentDependencies:
    """Load the LLM bundle, connector service, and checkpointer for one invoke.

    Uses the search space's default LLM config (``config_id=-1``). Per-step
    model overrides land in a future iteration alongside the ``model`` param.
    """
    llm, agent_config, err = await load_llm_bundle(
        session, config_id=-1, search_space_id=search_space_id
    )
    if err is not None or llm is None:
        raise DependencyError(err or "failed to load default LLM config")

    connector_service, firecrawl_api_key = await setup_connector_and_firecrawl(
        session, search_space_id=search_space_id
    )
    checkpointer = await get_chat_checkpointer()
    return AgentDependencies(
        llm=llm,
        agent_config=agent_config,
        connector_service=connector_service,
        firecrawl_api_key=firecrawl_api_key,
        checkpointer=checkpointer,
    )
