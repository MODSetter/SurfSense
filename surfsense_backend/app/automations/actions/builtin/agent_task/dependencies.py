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
from app.db import Workspace
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
    workspace_id: int,
    chat_model_id: int | None = None,
    image_gen_model_id: int | None = None,
    vision_model_id: int | None = None,
) -> AgentDependencies:
    """Load the LLM bundle, connector service, and a per-invoke in-memory checkpointer.

    Resolves the chat model from the automation's *captured* model snapshot
    (``chat_model_id``) so runs are insulated from later chat/workspace model
    changes. The model policy is enforced here as a runtime backstop: a captured
    model that is no longer billable (e.g. a premium global config was removed)
    fails the run clearly instead of silently consuming a free model.

    When ``chat_model_id`` is ``None`` (no captured snapshot — defensive fallback),
    fall back to the live workspace's ``chat_model_id`` and validate that.
    """
    if chat_model_id is not None:
        try:
            assert_models_billable(
                chat_model_id=chat_model_id,
                image_gen_model_id=image_gen_model_id,
                vision_model_id=vision_model_id,
            )
        except AutomationModelPolicyError as exc:
            raise DependencyError(str(exc)) from exc
        resolved_chat_model_id = chat_model_id or 0
    else:
        workspace = await session.get(Workspace, workspace_id)
        if workspace is None:
            raise DependencyError(f"workspace {workspace_id} not found")
        try:
            assert_automation_models_billable(workspace)
        except AutomationModelPolicyError as exc:
            raise DependencyError(str(exc)) from exc
        resolved_chat_model_id = workspace.chat_model_id or 0

    llm, agent_config, err = await load_llm_bundle(
        session,
        config_id=resolved_chat_model_id,
        workspace_id=workspace_id,
    )
    if err is not None or llm is None:
        raise DependencyError(err or "failed to load chat model config")

    connector_service, firecrawl_api_key = await setup_connector_and_firecrawl(
        session, workspace_id=workspace_id
    )
    # Per-task InMemorySaver: the shared Postgres checkpointer's connection
    # pool binds connections to the loop that opened them, but Celery uses a
    # fresh loop per task, so the next task hangs 30s on a dead-loop connection
    # (`PoolTimeout`). InMemorySaver has no pool and dies with the task — fine
    # while runs are one-shot (the checkpoint only spans one graph execution).
    #
    # TODO(checkpointer): when runs need durability (crash-resume or HITL
    # interrupt/resume across tasks), dispose the checkpointer pool around each
    # Celery task in `run_async_celery_task` — as `_dispose_shared_db_engine`
    # already does for the SQLAlchemy pool — then use the shared checkpointer.
    checkpointer = InMemorySaver()
    return AgentDependencies(
        llm=llm,
        agent_config=agent_config,
        connector_service=connector_service,
        firecrawl_api_key=firecrawl_api_key,
        checkpointer=checkpointer,
    )
