"""Load an LLM + AgentConfig bundle for a given config id.

Handles both code paths uniformly:
- ``config_id > 0`` → database-backed model-connection ``Model`` row.
- ``config_id < 0`` → virtual global model materialized from YAML/OpenRouter.

Returns ``(llm, agent_config, error_message)``; on success ``error_message`` is
``None``. The caller emits the friendly SSE error frame.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.chat.runtime.llm_config import (
    AgentConfig,
    SanitizedChatLiteLLM,
)
from app.config import config
from app.db import Model, Workspace
from app.services.model_capabilities import has_capability
from app.services.model_resolver import to_litellm
from app.services.token_tracking_service import register_model_usage_metadata


def _agent_config_from_resolved(
    *,
    config_id: int,
    config_name: str | None,
    provider: str,
    model_name: str,
    api_key: str | None,
    api_base: str | None,
    litellm_params: dict | None,
    supports_image_input: bool,
    billing_tier: str = "free",
) -> AgentConfig:
    return AgentConfig(
        provider=provider,
        model_name=model_name,
        api_key=api_key or "",
        api_base=api_base,
        custom_provider=None,
        litellm_params=litellm_params,
        config_id=config_id,
        config_name=config_name,
        is_auto_mode=False,
        billing_tier=billing_tier,
        is_premium=billing_tier == "premium",
        supports_image_input=supports_image_input,
    )


async def _load_workspace(
    session: AsyncSession, workspace_id: int
) -> Workspace | None:
    result = await session.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )
    return result.scalars().first()


async def _load_db_model(
    session: AsyncSession,
    *,
    model_id: int,
    workspace: Workspace,
) -> Model | None:
    result = await session.execute(
        select(Model)
        .options(selectinload(Model.connection))
        .where(Model.id == model_id, Model.enabled.is_(True))
    )
    model = result.scalars().first()
    if not model or not model.connection or not model.connection.enabled:
        return None
    conn = model.connection
    if conn.workspace_id is not None and conn.workspace_id != workspace.id:
        return None
    if conn.user_id is not None and conn.user_id != workspace.user_id:
        return None
    return model


async def load_llm_bundle(
    session: AsyncSession,
    *,
    config_id: int,
    workspace_id: int,
) -> tuple[Any, AgentConfig | None, str | None]:
    workspace = await _load_workspace(session, workspace_id)
    if not workspace:
        return None, None, f"Workspace {workspace_id} not found"

    if config_id > 0:
        model = await _load_db_model(
            session,
            model_id=config_id,
            workspace=workspace,
        )
        if not model or not has_capability(model, "chat"):
            return (
                None,
                None,
                f"Failed to load chat model with id {config_id}",
            )
        model_string, litellm_kwargs = to_litellm(model.connection, model.model_id)
        display_name = model.display_name or model.model_id
        provider = model.connection.provider or ""
        register_model_usage_metadata(
            model=model_string,
            model_ref=f"db:{model.id}",
            model_id=model.model_id,
            display_name=display_name,
            provider=provider,
        )
        agent_config = _agent_config_from_resolved(
            config_id=config_id,
            config_name=display_name,
            provider=provider,
            model_name=model.model_id,
            api_key=model.connection.api_key,
            api_base=model.connection.base_url,
            litellm_params=(model.connection.extra or {}).get("litellm_params"),
            supports_image_input=has_capability(model, "vision"),
            billing_tier="free",
        )
        return (
            SanitizedChatLiteLLM(
                model=model_string, **{**litellm_kwargs, "streaming": True}
            ),
            agent_config,
            None,
        )

    global_model = next(
        (m for m in config.GLOBAL_MODELS if m.get("id") == config_id), None
    )
    if not global_model or not has_capability(global_model, "chat"):
        return None, None, f"Failed to load global chat model with id {config_id}"
    global_connection = next(
        (
            c
            for c in config.GLOBAL_CONNECTIONS
            if c.get("id") == global_model.get("connection_id")
        ),
        None,
    )
    if not global_connection:
        return None, None, f"Failed to load global connection for model {config_id}"
    model_string, litellm_kwargs = to_litellm(
        global_connection, global_model["model_id"]
    )
    display_name = global_model.get("display_name") or global_model.get("model_id")
    provider = global_connection.get("provider") or ""
    register_model_usage_metadata(
        model=model_string,
        model_ref=f"global:{config_id}",
        model_id=global_model["model_id"],
        display_name=display_name,
        provider=provider,
    )
    agent_config = _agent_config_from_resolved(
        config_id=config_id,
        config_name=display_name,
        provider=provider,
        model_name=global_model["model_id"],
        api_key=global_connection.get("api_key"),
        api_base=global_connection.get("base_url"),
        litellm_params=(global_connection.get("extra") or {}).get("litellm_params"),
        supports_image_input=has_capability(global_model, "vision"),
        billing_tier=str(global_model.get("billing_tier", "free")).lower(),
    )
    return (
        SanitizedChatLiteLLM(
            model=model_string, **{**litellm_kwargs, "streaming": True}
        ),
        agent_config,
        None,
    )
