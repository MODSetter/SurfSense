"""Build the per-invocation dependencies the multi_agent_chat factory needs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy.ext.asyncio import AsyncSession

from app.automations.services.model_policy import (
    AutomationModelPolicyError,
    assert_automation_models_billable,
    assert_models_billable,
)
from app.db import SearchSpace
from app.tasks.chat.streaming.flows.shared.llm_bundle import load_llm_bundle
from app.tasks.chat.streaming.flows.shared.pre_stream_setup import (
    setup_connector_and_firecrawl,
)


class DependencyError(Exception):
    """An external dependency (LLM config, connector service, ...) refused to load."""


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
    agent_llm_id: int | None = None,
    image_generation_config_id: int | None = None,
    vision_llm_config_id: int | None = None,
) -> AgentDependencies:
    """Load the LLM bundle, connector service, and a per-invoke in-memory checkpointer.

    Resolves the agent LLM from the automation's *captured* model snapshot
    (``agent_llm_id``) so runs are insulated from later chat/search-space model
    changes. The model policy is enforced here as a runtime backstop: a captured
    model that is no longer billable (e.g. a premium global config was removed)
    fails the run clearly instead of silently consuming a free model.

    When ``agent_llm_id`` is ``None`` (no captured snapshot — defensive fallback),
    fall back to the live search space's ``agent_llm_id`` and validate that.
    """
    if agent_llm_id is not None:
        try:
            assert_models_billable(
                agent_llm_id=agent_llm_id,
                image_generation_config_id=image_generation_config_id,
                vision_llm_config_id=vision_llm_config_id,
            )
        except AutomationModelPolicyError as exc:
            raise DependencyError(str(exc)) from exc
        resolved_agent_llm_id = agent_llm_id or 0
    else:
        search_space = await session.get(SearchSpace, search_space_id)
        if search_space is None:
            raise DependencyError(f"search space {search_space_id} not found")
        try:
            assert_automation_models_billable(search_space)
        except AutomationModelPolicyError as exc:
            raise DependencyError(str(exc)) from exc
        resolved_agent_llm_id = search_space.agent_llm_id or 0

    llm, agent_config, err = await load_llm_bundle(
        session,
        config_id=resolved_agent_llm_id,
        search_space_id=search_space_id,
    )
    if err is not None or llm is None:
        raise DependencyError(err or "failed to load agent LLM config")

    connector_service, firecrawl_api_key = await setup_connector_and_firecrawl(
        session, search_space_id=search_space_id
    )
    # Quick fix: use an in-memory checkpointer for automation runs.
    #
    # The shared Postgres checkpointer caches DB connections in a
    # module-level pool. Each cached connection is bound to the asyncio
    # loop that opened it. Celery throws away the loop after every task,
    # so the pool ends up full of connections pointing to a dead loop,
    # and the next Celery task (running on a fresh loop) can't use any
    # of them — it hangs 30s and fails with
    # `PoolTimeout: couldn't get a connection after 30.00 sec`.
    #
    # InMemorySaver has no cached connections, no loop binding — each
    # Celery task creates one and drops it on exit.
    #
    # TODO(checkpointer): proper fix is to dispose the checkpointer
    # pool around each Celery task in `run_async_celery_task`, the same
    # way `_dispose_shared_db_engine` already does for the SQLAlchemy
    # pool. Then this site can switch back to the shared checkpointer.
    checkpointer = InMemorySaver()
    return AgentDependencies(
        llm=llm,
        agent_config=agent_config,
        connector_service=connector_service,
        firecrawl_api_key=firecrawl_api_key,
        checkpointer=checkpointer,
    )
