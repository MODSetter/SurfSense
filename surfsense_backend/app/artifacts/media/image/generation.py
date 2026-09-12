"""Shared image-model invocation below standalone-image persistence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from litellm import aimage_generation
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import Model, Workspace
from app.services.auto_model_pin_service import (
    auto_model_candidates,
    choose_auto_model_candidate,
)
from app.services.billable_calls import billable_call
from app.services.image_gen_billing import resolve_billing_for_image_gen
from app.services.image_gen_router_service import (
    IMAGE_GEN_AUTO_MODE_ID,
    is_image_gen_auto_mode,
)
from app.services.llm_service import get_global_connection, get_global_model
from app.services.model_capabilities import has_capability
from app.services.model_resolver import to_litellm


@dataclass(frozen=True, slots=True)
class ImageGenerationResult:
    response: dict[str, Any]
    config_id: int
    provider_model: str | None


async def generate_image_response(
    session: AsyncSession,
    *,
    workspace_id: int,
    prompt: str,
    n: int = 1,
    image_gen_model_id_override: int | None = None,
    usage_type: str = "image_generation",
) -> ImageGenerationResult:
    """Resolve, bill, invoke, and normalize one workspace image model call."""
    workspace_result = await session.execute(
        select(Workspace).filter(Workspace.id == workspace_id)
    )
    workspace = workspace_result.scalars().first()
    if not workspace:
        raise ValueError("Workspace not found")

    config_id = (
        image_gen_model_id_override or IMAGE_GEN_AUTO_MODE_ID
        if image_gen_model_id_override is not None
        else workspace.image_gen_model_id or IMAGE_GEN_AUTO_MODE_ID
    )
    gen_kwargs: dict[str, Any] = {}
    if n > 1:
        gen_kwargs["n"] = n

    if is_image_gen_auto_mode(config_id):
        candidates = await auto_model_candidates(
            session,
            workspace_id=workspace_id,
            user_id=workspace.user_id,
            capability="image_gen",
        )
        if not candidates:
            raise ValueError(
                "No image generation models available. "
                "Please add an image model in Settings > Image Models."
            )
        config_id = int(
            choose_auto_model_candidate(candidates, workspace_id)["id"]
        )

    provider_base_url: str | None = None
    if config_id < 0:
        global_model = get_global_model(config_id)
        if not global_model or not has_capability(global_model, "image_gen"):
            raise ValueError(f"Image generation model {config_id} not found")
        global_connection = get_global_connection(global_model["connection_id"])
        if not global_connection:
            raise ValueError(
                f"Image generation connection for model {config_id} not found"
            )
        model_string, resolved_kwargs = to_litellm(
            global_connection,
            global_model["model_id"],
        )
    else:
        model_result = await session.execute(
            select(Model)
            .options(selectinload(Model.connection))
            .filter(Model.id == config_id, Model.enabled.is_(True))
        )
        db_model = model_result.scalars().first()
        if not db_model or not db_model.connection or not db_model.connection.enabled:
            raise ValueError(f"Image generation model {config_id} not found")
        connection = db_model.connection
        if connection.workspace_id is not None and connection.workspace_id != workspace_id:
            raise ValueError(f"Image generation model {config_id} not found")
        if connection.user_id is not None and connection.user_id != workspace.user_id:
            raise ValueError(f"Image generation model {config_id} not found")
        if not has_capability(db_model, "image_gen"):
            raise ValueError(f"Model {config_id} is not image-generation capable")
        model_string, resolved_kwargs = to_litellm(
            connection,
            db_model.model_id,
        )

    gen_kwargs.update(resolved_kwargs)
    provider_base_url = resolved_kwargs.get("api_base")
    billing_tier, base_model, reserve_micros = await resolve_billing_for_image_gen(
        session,
        config_id,
        workspace,
    )
    async with billable_call(
        user_id=workspace.user_id,
        workspace_id=workspace_id,
        billing_tier=billing_tier,
        base_model=base_model,
        quota_reserve_micros_override=reserve_micros,
        usage_type=usage_type,
        call_details={"model": base_model, "prompt": prompt[:100]},
    ):
        response = await aimage_generation(
            prompt=prompt,
            model=model_string,
            **gen_kwargs,
        )

    response_dict = (
        response.model_dump() if hasattr(response, "model_dump") else dict(response)
    )
    for image in response_dict.get("data") or []:
        raw_url = image.get("url") if isinstance(image, dict) else None
        if raw_url and raw_url.startswith("/") and provider_base_url:
            parsed = urlparse(provider_base_url)
            image["url"] = f"{parsed.scheme}://{parsed.netloc}{raw_url}"

    provider_model = getattr(response, "_hidden_params", {}).get("model")
    return ImageGenerationResult(
        response=response_dict,
        config_id=config_id,
        provider_model=provider_model if isinstance(provider_model, str) else None,
    )


__all__ = ["ImageGenerationResult", "generate_image_response"]
