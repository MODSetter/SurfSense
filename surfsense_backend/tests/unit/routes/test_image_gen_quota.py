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

    async def _no_auto_candidates(*_args, **_kwargs):
        return []

    monkeypatch.setattr(
        image_generation_routes,
        "auto_model_candidates",
        _no_auto_candidates,
    )

    workspace = SimpleNamespace(id=1, user_id=None, image_gen_model_id=None)
    tier, model, reserve = await image_generation_routes._resolve_billing_for_image_gen(
        session=None,
        config_id=0,  # IMAGE_GEN_AUTO_MODE_ID
        workspace=workspace,
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
        "GLOBAL_MODELS",
        [
            {
                "id": -1,
                "connection_id": -101,
                "model_id": "gpt-image-1",
                "billing_tier": "premium",
                "catalog": {"quota_reserve_micros": 75_000},
            },
            {
                "id": -2,
                "connection_id": -102,
                "model_id": "google/gemini-2.5-flash-image",
                "billing_tier": "free",
                "catalog": {},
            },
        ],
        raising=False,
    )
    monkeypatch.setattr(
        config,
        "GLOBAL_CONNECTIONS",
        [
            {
                "id": -101,
                "provider": "openai",
                "api_key": "sk-test",
                "base_url": None,
                "extra": {},
            },
            {
                "id": -102,
                "provider": "openrouter",
                "api_key": "sk-or-test",
                "base_url": "https://openrouter.ai/api/v1",
                "extra": {},
            },
        ],
        raising=False,
    )

    workspace = SimpleNamespace(id=1, user_id=None, image_gen_model_id=None)

    # Premium with override.
    tier, model, reserve = await image_generation_routes._resolve_billing_for_image_gen(
        session=None, config_id=-1, workspace=workspace
    )
    assert tier == "premium"
    assert model == "openai/gpt-image-1"
    assert reserve == 75_000

    # Free, no override → falls back to default.
    from app.services.billable_calls import DEFAULT_IMAGE_RESERVE_MICROS

    tier, model, reserve = await image_generation_routes._resolve_billing_for_image_gen(
        session=None, config_id=-2, workspace=workspace
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

    workspace = SimpleNamespace(id=1, user_id=None, image_gen_model_id=None)
    tier, model, reserve = await image_generation_routes._resolve_billing_for_image_gen(
        session=None, config_id=42, workspace=workspace
    )
    assert tier == "free"
    assert model == "user_byok"
    assert reserve == DEFAULT_IMAGE_RESERVE_MICROS


@pytest.mark.asyncio
async def test_resolve_billing_falls_back_to_workspace_default(monkeypatch):
    """When the request omits ``image_gen_model_id``, the helper
    must consult the workspace's default — so a workspace pinned
    to a premium global config still gates new requests by quota.
    """
    from app.config import config
    from app.routes import image_generation_routes

    monkeypatch.setattr(
        config,
        "GLOBAL_MODELS",
        [
            {
                "id": -7,
                "connection_id": -101,
                "model_id": "gpt-image-1",
                "billing_tier": "premium",
                "catalog": {},
            }
        ],
        raising=False,
    )
    monkeypatch.setattr(
        config,
        "GLOBAL_CONNECTIONS",
        [
            {
                "id": -101,
                "provider": "openai",
                "api_key": "sk-test",
                "base_url": None,
                "extra": {},
            }
        ],
        raising=False,
    )

    workspace = SimpleNamespace(id=1, user_id=None, image_gen_model_id=-7)
    (
        tier,
        model,
        _reserve,
    ) = await image_generation_routes._resolve_billing_for_image_gen(
        session=None, config_id=None, workspace=workspace
    )
    assert tier == "premium"
    assert model == "openai/gpt-image-1"
