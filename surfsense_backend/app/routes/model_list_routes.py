"""
API route for fetching the available models catalogue.

Serves a dynamically-updated list sourced from the OpenRouter public API,
with a local JSON fallback when the API is unreachable.

Also exposes a /models/system endpoint that returns the system-managed models
from global_llm_config.yaml for use in cloud/hosted mode (no BYOK).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.config import config
from app.db import User
from app.services.model_list_service import get_model_list
from app.users import current_active_user

router = APIRouter()
logger = logging.getLogger(__name__)


class ModelListItem(BaseModel):
    value: str
    label: str
    provider: str
    context_window: str | None = None


class SystemModelItem(BaseModel):
    """A system-managed model available in cloud mode."""

    id: int  # Negative ID from global_llm_config.yaml (e.g. -1, -2)
    name: str
    description: str | None = None
    provider: str
    model_name: str
    tier_required: str = "free"  # "free" | "pro" | "enterprise"


def _get_tier_for_model(provider: str, model_name: str) -> str:
    """
    Derive the subscription tier required to use a given model.

    Rules (adjust as pricing plans are defined):
    - GPT-4 class, Claude 3 Opus, Gemini Ultra → pro
    - Everything else → free
    """
    model_lower = model_name.lower()

    # Pro-tier models: high-capability / expensive models
    pro_patterns = [
        "gpt-4",
        "claude-3-opus",
        "claude-3-5-sonnet",
        "claude-3-7-sonnet",
        "gemini-1.5-pro",
        "gemini-2.0-pro",
        "gemini-2.5-pro",
        "llama3-70b",
        "llama-3-70b",
        "mistral-large",
    ]
    for pattern in pro_patterns:
        if pattern in model_lower:
            return "pro"

    return "free"


def get_tier_for_model_id(model_id: int) -> str:
    """
    Look up the tier_required for a given system model ID.

    Used by chat routes to enforce tier at request time.
    Prefers explicit `tier_required` from YAML; falls back to pattern matching.

    Returns:
        The tier string ("free", "pro", "enterprise") or "free" if not found.
    """
    global_configs = config.GLOBAL_LLM_CONFIGS
    if not global_configs:
        return "free"

    for cfg in global_configs:
        if cfg.get("id") == model_id:
            # Prefer explicit tier from YAML config
            explicit_tier = cfg.get("tier_required")
            if explicit_tier:
                return str(explicit_tier).lower()
            # Fall back to pattern-based inference
            provider = str(cfg.get("provider", "UNKNOWN"))
            model_name = str(cfg.get("model_name", ""))
            return _get_tier_for_model(provider, model_name)

    return "free"


@router.get("/models", response_model=list[ModelListItem])
async def list_available_models(
    user: User = Depends(current_active_user),
):
    """
    Return all available models grouped by provider (BYOK / self-hosted mode).

    The list is sourced from the OpenRouter public API and cached for 1 hour.
    If the API is unreachable, a local fallback file is used instead.
    """
    try:
        return await get_model_list()
    except Exception as e:
        logger.exception("Failed to fetch model list")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch model list: {e!s}"
        ) from e


@router.get("/models/system", response_model=list[SystemModelItem])
async def list_system_models(
    user: User = Depends(current_active_user),
):
    """
    Return system-managed models from global_llm_config.yaml (cloud mode).

    Models are annotated with a `tier_required` field so the frontend can
    show which models require a paid subscription plan.  The caller's current
    subscription status is NOT checked here — enforcement happens at chat time.

    Only available in cloud mode.
    """
    if not config.is_cloud():
        raise HTTPException(
            status_code=404,
            detail="System models are only available in cloud mode.",
        )
    global_configs = config.GLOBAL_LLM_CONFIGS
    if not global_configs:
        return []

    items: list[SystemModelItem] = []
    for cfg in global_configs:
        cfg_id = cfg.get("id")
        if cfg_id is None or cfg_id >= 0:
            # Skip auto-mode (0) and any mistakenly positive IDs
            continue

        provider = str(cfg.get("provider", "UNKNOWN"))
        model_name = str(cfg.get("model_name", ""))
        # Prefer explicit tier from YAML; fall back to pattern matching
        explicit_tier = cfg.get("tier_required")
        tier = str(explicit_tier).lower() if explicit_tier else _get_tier_for_model(provider, model_name)
        items.append(
            SystemModelItem(
                id=cfg_id,
                name=str(cfg.get("name", model_name)),
                description=cfg.get("description"),
                provider=provider,
                model_name=model_name,
                tier_required=tier,
            )
        )

    return items
