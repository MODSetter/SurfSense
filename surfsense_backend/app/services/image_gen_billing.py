"""Billing resolution for image generation."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Workspace
from app.services.auto_model_pin_service import (
    auto_model_candidates,
    choose_auto_model_candidate,
)
from app.services.billable_calls import DEFAULT_IMAGE_RESERVE_MICROS
from app.services.image_gen_router_service import (
    IMAGE_GEN_AUTO_MODE_ID,
    is_image_gen_auto_mode,
)
from app.services.llm_service import get_global_connection, get_global_model
from app.services.model_resolver import to_litellm


async def resolve_billing_for_image_gen(
    session: AsyncSession,
    config_id: int | None,
    workspace: Workspace,
) -> tuple[str, str, int]:
    """Resolve ``(billing_tier, base_model, reserve_micros)`` for a request.

    Runs *before* ``billable_call`` so the reservation is sized for the config
    that will actually run, and so a request about to 402 never reaches the
    provider. User-owned (positive ID) BYOK models are always free — they cost
    us nothing. Auto mode resolves to one concrete model before billing.
    """
    resolved_id = config_id
    if resolved_id is None:
        resolved_id = workspace.image_gen_model_id or IMAGE_GEN_AUTO_MODE_ID

    if is_image_gen_auto_mode(resolved_id):
        candidates = await auto_model_candidates(
            session,
            workspace_id=workspace.id,
            user_id=workspace.user_id,
            capability="image_gen",
        )
        if not candidates:
            return ("free", "auto", DEFAULT_IMAGE_RESERVE_MICROS)
        resolved_id = int(choose_auto_model_candidate(candidates, workspace.id)["id"])

    if resolved_id < 0:
        global_model = get_global_model(resolved_id) or {}
        global_connection = get_global_connection(global_model.get("connection_id", 0))
        billing_tier = str(global_model.get("billing_tier", "free")).lower()
        if global_connection and global_model.get("model_id"):
            base_model, _ = to_litellm(global_connection, global_model["model_id"])
        else:
            base_model = "global_image_model"
        catalog = global_model.get("catalog") or {}
        reserve_micros = int(
            catalog.get("quota_reserve_micros") or DEFAULT_IMAGE_RESERVE_MICROS
        )
        return (billing_tier, base_model, reserve_micros)

    return ("free", "user_byok", DEFAULT_IMAGE_RESERVE_MICROS)
