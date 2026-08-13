"""Resolve which image model a request runs against.

Two callers with different trust models share one output shape:
- workspace door: reads the workspace's configured model (or Auto), enforces
  BYOK ownership, and returns ``config_id`` so billing can size a reserve.
- anonymous door: picks a designated global model flagged ``anonymous_enabled``
  in ``GLOBAL_IMAGE_GEN_CONFIGS`` (no workspace, no billing).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import config
from app.db import Model, Workspace
from app.services.auto_model_pin_service import (
    auto_model_candidates,
    choose_auto_model_candidate,
)
from app.services.image_gen_router_service import (
    IMAGE_GEN_AUTO_MODE_ID,
    is_image_gen_auto_mode,
)
from app.services.llm_service import get_global_connection, get_global_model
from app.services.model_capabilities import has_capability
from app.services.model_resolver import native_connection_from_config, to_litellm


class ImageModelUnavailableError(Exception):
    """No usable image-generation model could be resolved for the request."""


@dataclass(frozen=True)
class ResolvedImageModel:
    """Everything the executor needs to call the provider once."""

    model_string: str
    gen_kwargs: dict[str, Any] = field(default_factory=dict)
    provider_base_url: str | None = None
    # None for anonymous/global-only resolution; positive/negative id otherwise.
    config_id: int | None = None


async def resolve_workspace_image_model(
    session: AsyncSession,
    *,
    workspace: Workspace,
    image_gen_model_id_override: int | None = None,
) -> ResolvedImageModel:
    """Resolve the model for an authenticated workspace request.

    ``image_gen_model_id_override`` insulates automation runs from later
    workspace changes by pinning a captured model id.
    """
    if image_gen_model_id_override is not None:
        config_id = image_gen_model_id_override or IMAGE_GEN_AUTO_MODE_ID
    else:
        config_id = workspace.image_gen_model_id or IMAGE_GEN_AUTO_MODE_ID

    if is_image_gen_auto_mode(config_id):
        candidates = await auto_model_candidates(
            session,
            workspace_id=workspace.id,
            user_id=workspace.user_id,
            capability="image_gen",
        )
        if not candidates:
            raise ImageModelUnavailableError(
                "No image generation models available. "
                "Please add an image model in Settings > Image Models."
            )
        config_id = int(choose_auto_model_candidate(candidates, workspace.id)["id"])

    if config_id < 0:
        return _resolve_global(config_id)

    return await _resolve_byok(session, config_id, workspace)


def _resolve_global(config_id: int) -> ResolvedImageModel:
    global_model = get_global_model(config_id)
    if not global_model or not has_capability(global_model, "image_gen"):
        raise ImageModelUnavailableError(f"Image generation model {config_id} not found")
    global_connection = get_global_connection(global_model["connection_id"])
    if not global_connection:
        raise ImageModelUnavailableError(
            f"Image generation connection for model {config_id} not found"
        )
    model_string, resolved_kwargs = to_litellm(
        global_connection, global_model["model_id"]
    )
    return ResolvedImageModel(
        model_string=model_string,
        gen_kwargs=resolved_kwargs,
        provider_base_url=resolved_kwargs.get("api_base"),
        config_id=config_id,
    )


async def _resolve_byok(
    session: AsyncSession, config_id: int, workspace: Workspace
) -> ResolvedImageModel:
    result = await session.execute(
        select(Model)
        .options(selectinload(Model.connection))
        .filter(Model.id == config_id, Model.enabled.is_(True))
    )
    db_model = result.scalars().first()
    if not db_model or not db_model.connection or not db_model.connection.enabled:
        raise ImageModelUnavailableError(f"Image generation model {config_id} not found")
    conn = db_model.connection
    if conn.workspace_id is not None and conn.workspace_id != workspace.id:
        raise ImageModelUnavailableError(f"Image generation model {config_id} not found")
    if conn.user_id is not None and conn.user_id != workspace.user_id:
        raise ImageModelUnavailableError(f"Image generation model {config_id} not found")
    if not has_capability(db_model, "image_gen"):
        raise ImageModelUnavailableError(
            f"Model {config_id} is not image-generation capable"
        )
    model_string, resolved_kwargs = to_litellm(db_model.connection, db_model.model_id)
    return ResolvedImageModel(
        model_string=model_string,
        gen_kwargs=resolved_kwargs,
        provider_base_url=resolved_kwargs.get("api_base"),
        config_id=config_id,
    )


def anonymous_image_config(seo_slug: str | None = None) -> dict[str, Any] | None:
    """The image config flagged for anonymous use, or None when none exists."""
    for cfg in config.GLOBAL_IMAGE_GEN_CONFIGS:
        if not isinstance(cfg, dict) or not cfg.get("anonymous_enabled", False):
            continue
        if seo_slug is not None and cfg.get("seo_slug") != seo_slug:
            continue
        return cfg
    return None


def resolve_anonymous_image_model(seo_slug: str | None = None) -> ResolvedImageModel:
    """Resolve the designated cheap funnel model for anonymous callers."""
    cfg = anonymous_image_config(seo_slug)
    if cfg is None or not cfg.get("model_name"):
        raise ImageModelUnavailableError(
            "No image model is enabled for anonymous use."
        )
    model_string, resolved_kwargs = to_litellm(
        native_connection_from_config(cfg), cfg["model_name"]
    )
    return ResolvedImageModel(
        model_string=model_string,
        gen_kwargs=resolved_kwargs,
        provider_base_url=resolved_kwargs.get("api_base"),
        config_id=None,
    )
