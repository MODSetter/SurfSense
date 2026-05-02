"""Unit tests for the image-generation route's billing-resolution helper.

End-to-end "POST /image-generations returns 402" coverage requires the
integration harness (real DB, real auth) and lives in
``tests/integration/document_upload/`` alongside the other quota tests.
This unit test focuses on the new ``_resolve_billing_for_image_gen``
helper which:

* Returns ``free`` for Auto mode, even when premium configs exist
  (Auto-mode billing-tier surfacing is a follow-up).
* Returns ``free`` for user-owned BYOK configs (positive IDs).
* Returns the global config's ``billing_tier`` for negative IDs.
* Honours the per-config ``quota_reserve_micros`` override when present.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_resolve_billing_for_auto_mode(monkeypatch):
    from app.routes import image_generation_routes
    from app.services.billable_calls import DEFAULT_IMAGE_RESERVE_MICROS

    search_space = SimpleNamespace(image_generation_config_id=None)
    tier, model, reserve = await image_generation_routes._resolve_billing_for_image_gen(
        session=None,  # Not consumed on this code path.
        config_id=0,  # IMAGE_GEN_AUTO_MODE_ID
        search_space=search_space,
    )
    assert tier == "free"
    assert model == "auto"
    assert reserve == DEFAULT_IMAGE_RESERVE_MICROS


@pytest.mark.asyncio
async def test_resolve_billing_for_premium_global_config(monkeypatch):
    from app.config import config
    from app.routes import image_generation_routes

    monkeypatch.setattr(
        config,
        "GLOBAL_IMAGE_GEN_CONFIGS",
        [
            {
                "id": -1,
                "provider": "OPENAI",
                "model_name": "gpt-image-1",
                "billing_tier": "premium",
                "quota_reserve_micros": 75_000,
            },
            {
                "id": -2,
                "provider": "OPENROUTER",
                "model_name": "google/gemini-2.5-flash-image",
                "billing_tier": "free",
            },
        ],
        raising=False,
    )

    search_space = SimpleNamespace(image_generation_config_id=None)

    # Premium with override.
    tier, model, reserve = await image_generation_routes._resolve_billing_for_image_gen(
        session=None, config_id=-1, search_space=search_space
    )
    assert tier == "premium"
    assert model == "openai/gpt-image-1"
    assert reserve == 75_000

    # Free, no override → falls back to default.
    from app.services.billable_calls import DEFAULT_IMAGE_RESERVE_MICROS

    tier, model, reserve = await image_generation_routes._resolve_billing_for_image_gen(
        session=None, config_id=-2, search_space=search_space
    )
    assert tier == "free"
    # Provider-prefixed model string for OpenRouter.
    assert "google/gemini-2.5-flash-image" in model
    assert reserve == DEFAULT_IMAGE_RESERVE_MICROS


@pytest.mark.asyncio
async def test_resolve_billing_for_user_owned_byok_is_free():
    """User-owned BYOK configs (positive IDs) cost the user nothing on
    our side — they pay the provider directly. Always free.
    """
    from app.routes import image_generation_routes
    from app.services.billable_calls import DEFAULT_IMAGE_RESERVE_MICROS

    search_space = SimpleNamespace(image_generation_config_id=None)
    tier, model, reserve = await image_generation_routes._resolve_billing_for_image_gen(
        session=None, config_id=42, search_space=search_space
    )
    assert tier == "free"
    assert model == "user_byok"
    assert reserve == DEFAULT_IMAGE_RESERVE_MICROS


@pytest.mark.asyncio
async def test_resolve_billing_falls_back_to_search_space_default(monkeypatch):
    """When the request omits ``image_generation_config_id``, the helper
    must consult the search space's default — so a search space pinned
    to a premium global config still gates new requests by quota.
    """
    from app.config import config
    from app.routes import image_generation_routes

    monkeypatch.setattr(
        config,
        "GLOBAL_IMAGE_GEN_CONFIGS",
        [
            {
                "id": -7,
                "provider": "OPENAI",
                "model_name": "gpt-image-1",
                "billing_tier": "premium",
            }
        ],
        raising=False,
    )

    search_space = SimpleNamespace(image_generation_config_id=-7)
    (
        tier,
        model,
        _reserve,
    ) = await image_generation_routes._resolve_billing_for_image_gen(
        session=None, config_id=None, search_space=search_space
    )
    assert tier == "premium"
    assert model == "openai/gpt-image-1"
