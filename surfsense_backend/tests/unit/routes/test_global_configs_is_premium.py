"""Unit tests for ``is_premium`` derivation on the global image-gen and
vision-LLM list endpoints.

Chat globals (``GET /global-llm-configs``) already emit
``is_premium = (billing_tier == "premium")``. Image and vision did not,
which made the new-chat ``model-selector`` render the Free/Premium badge
on the Chat tab but skip it on the Image and Vision tabs (the selector
keys its badge logic off ``is_premium``). These tests pin parity:

* YAML free entry → ``is_premium=False``
* YAML premium entry → ``is_premium=True``
* OpenRouter dynamic premium entry → ``is_premium=True``
* Auto stub (always emitted when at least one config is present)
  → ``is_premium=False``
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


_IMAGE_FIXTURE: list[dict] = [
    {
        "id": -1,
        "name": "DALL-E 3",
        "provider": "OPENAI",
        "model_name": "dall-e-3",
        "api_key": "sk-test",
        "billing_tier": "free",
    },
    {
        "id": -2,
        "name": "GPT-Image 1 (premium)",
        "provider": "OPENAI",
        "model_name": "gpt-image-1",
        "api_key": "sk-test",
        "billing_tier": "premium",
    },
    {
        "id": -20_001,
        "name": "google/gemini-2.5-flash-image (OpenRouter)",
        "provider": "OPENROUTER",
        "model_name": "google/gemini-2.5-flash-image",
        "api_key": "sk-or-test",
        "api_base": "https://openrouter.ai/api/v1",
        "billing_tier": "premium",
    },
]


_VISION_FIXTURE: list[dict] = [
    {
        "id": -1,
        "name": "GPT-4o Vision",
        "provider": "OPENAI",
        "model_name": "gpt-4o",
        "api_key": "sk-test",
        "billing_tier": "free",
    },
    {
        "id": -2,
        "name": "Claude 3.5 Sonnet (premium)",
        "provider": "ANTHROPIC",
        "model_name": "claude-3-5-sonnet",
        "api_key": "sk-ant-test",
        "billing_tier": "premium",
    },
    {
        "id": -30_001,
        "name": "openai/gpt-4o (OpenRouter)",
        "provider": "OPENROUTER",
        "model_name": "openai/gpt-4o",
        "api_key": "sk-or-test",
        "api_base": "https://openrouter.ai/api/v1",
        "billing_tier": "premium",
    },
]


# =============================================================================
# Image generation
# =============================================================================


@pytest.mark.asyncio
async def test_global_image_gen_configs_emit_is_premium(monkeypatch):
    """Each emitted config must carry ``is_premium`` derived server-side
    from ``billing_tier``. The Auto stub is always free.
    """
    from app.config import config
    from app.routes import image_generation_routes

    monkeypatch.setattr(
        config, "GLOBAL_IMAGE_GEN_CONFIGS", _IMAGE_FIXTURE, raising=False
    )

    payload = await image_generation_routes.get_global_image_gen_configs(user=None)

    by_id = {c["id"]: c for c in payload}

    # Auto stub is always emitted when at least one global config exists,
    # and it must always declare itself free (Auto-mode billing-tier
    # surfacing is a separate follow-up).
    assert 0 in by_id, "Auto stub should be emitted when at least one config exists"
    assert by_id[0]["is_premium"] is False
    assert by_id[0]["billing_tier"] == "free"

    # YAML free entry — ``is_premium=False``
    assert by_id[-1]["is_premium"] is False
    assert by_id[-1]["billing_tier"] == "free"

    # YAML premium entry — ``is_premium=True``
    assert by_id[-2]["is_premium"] is True
    assert by_id[-2]["billing_tier"] == "premium"

    # OpenRouter dynamic premium entry — same field, same derivation
    assert by_id[-20_001]["is_premium"] is True
    assert by_id[-20_001]["billing_tier"] == "premium"

    # Every emitted dict (including Auto) must have the field — never missing.
    for cfg in payload:
        assert "is_premium" in cfg, f"is_premium missing from {cfg.get('id')}"
        assert isinstance(cfg["is_premium"], bool)


@pytest.mark.asyncio
async def test_global_image_gen_configs_no_globals_no_auto_stub(monkeypatch):
    """When there are no global configs at all, the endpoint emits an
    empty list (no Auto stub) — Auto mode would have nothing to route to.
    """
    from app.config import config
    from app.routes import image_generation_routes

    monkeypatch.setattr(config, "GLOBAL_IMAGE_GEN_CONFIGS", [], raising=False)
    payload = await image_generation_routes.get_global_image_gen_configs(user=None)
    assert payload == []


# =============================================================================
# Vision LLM
# =============================================================================


@pytest.mark.asyncio
async def test_global_vision_llm_configs_emit_is_premium(monkeypatch):
    from app.config import config
    from app.routes import vision_llm_routes

    monkeypatch.setattr(
        config, "GLOBAL_VISION_LLM_CONFIGS", _VISION_FIXTURE, raising=False
    )

    payload = await vision_llm_routes.get_global_vision_llm_configs(user=None)

    by_id = {c["id"]: c for c in payload}

    assert 0 in by_id, "Auto stub should be emitted when at least one config exists"
    assert by_id[0]["is_premium"] is False
    assert by_id[0]["billing_tier"] == "free"

    assert by_id[-1]["is_premium"] is False
    assert by_id[-1]["billing_tier"] == "free"

    assert by_id[-2]["is_premium"] is True
    assert by_id[-2]["billing_tier"] == "premium"

    assert by_id[-30_001]["is_premium"] is True
    assert by_id[-30_001]["billing_tier"] == "premium"

    for cfg in payload:
        assert "is_premium" in cfg, f"is_premium missing from {cfg.get('id')}"
        assert isinstance(cfg["is_premium"], bool)


@pytest.mark.asyncio
async def test_global_vision_llm_configs_no_globals_no_auto_stub(monkeypatch):
    from app.config import config
    from app.routes import vision_llm_routes

    monkeypatch.setattr(config, "GLOBAL_VISION_LLM_CONFIGS", [], raising=False)
    payload = await vision_llm_routes.get_global_vision_llm_configs(user=None)
    assert payload == []
