"""Unit tests for the dynamic OpenRouter integration."""

from __future__ import annotations

import pytest

from app.services.openrouter_integration_service import (
    _OPENROUTER_DYNAMIC_MARKER,
    _generate_configs,
    _openrouter_tier,
    _stable_config_id,
)

pytestmark = pytest.mark.unit


def _minimal_openrouter_model(
    *,
    model_id: str,
    pricing: dict | None = None,
    name: str | None = None,
) -> dict:
    """Return a synthetic OpenRouter /api/v1/models entry.

    The real API payload includes a lot of fields; we only populate what
    ``_generate_configs`` actually inspects (architecture, tool support,
    context, pricing, id).
    """
    return {
        "id": model_id,
        "name": name or model_id,
        "architecture": {"output_modalities": ["text"]},
        "supported_parameters": ["tools"],
        "context_length": 200_000,
        "pricing": pricing or {"prompt": "0.000003", "completion": "0.000015"},
    }


# ---------------------------------------------------------------------------
# _openrouter_tier
# ---------------------------------------------------------------------------


def test_openrouter_tier_free_suffix():
    assert _openrouter_tier({"id": "foo/bar:free"}) == "free"


def test_openrouter_tier_zero_pricing():
    model = {
        "id": "foo/bar",
        "pricing": {"prompt": "0", "completion": "0"},
    }
    assert _openrouter_tier(model) == "free"


def test_openrouter_tier_paid():
    model = {
        "id": "foo/bar",
        "pricing": {"prompt": "0.000003", "completion": "0.000015"},
    }
    assert _openrouter_tier(model) == "premium"


def test_openrouter_tier_missing_pricing_is_premium():
    assert _openrouter_tier({"id": "foo/bar"}) == "premium"
    assert _openrouter_tier({"id": "foo/bar", "pricing": {}}) == "premium"


# ---------------------------------------------------------------------------
# _stable_config_id
# ---------------------------------------------------------------------------


def test_stable_config_id_deterministic():
    taken1: set[int] = set()
    taken2: set[int] = set()
    a = _stable_config_id("openai/gpt-4o", -10_000, taken1)
    b = _stable_config_id("openai/gpt-4o", -10_000, taken2)
    assert a == b
    assert a < 0


def test_stable_config_id_collision_decrements():
    """When two model_ids hash to the same slot, the second should decrement."""
    taken: set[int] = set()
    a = _stable_config_id("openai/gpt-4o", -10_000, taken)
    # Force a collision by pre-populating ``taken`` with a slot we know will be
    # picked.
    taken_forced = {a}
    b = _stable_config_id("openai/gpt-4o", -10_000, taken_forced)
    assert b != a
    assert b == a - 1
    assert b in taken_forced


def test_stable_config_id_different_models_different_ids():
    taken: set[int] = set()
    ids = {
        _stable_config_id("openai/gpt-4o", -10_000, taken),
        _stable_config_id("anthropic/claude-3.5-sonnet", -10_000, taken),
        _stable_config_id("google/gemini-2.0-flash", -10_000, taken),
    }
    assert len(ids) == 3


def test_stable_config_id_survives_catalogue_churn():
    """Removing a model should not shift other models' IDs (the bug we fix)."""
    taken1: set[int] = set()
    id_a1 = _stable_config_id("openai/gpt-4o", -10_000, taken1)
    _ = _stable_config_id("anthropic/claude-3-haiku", -10_000, taken1)
    id_c1 = _stable_config_id("google/gemini-2.0-flash", -10_000, taken1)

    taken2: set[int] = set()
    id_a2 = _stable_config_id("openai/gpt-4o", -10_000, taken2)
    id_c2 = _stable_config_id("google/gemini-2.0-flash", -10_000, taken2)

    assert id_a1 == id_a2
    assert id_c1 == id_c2


# ---------------------------------------------------------------------------
# _generate_configs
# ---------------------------------------------------------------------------


_SETTINGS_BASE: dict = {
    "api_key": "sk-or-test",
    "id_offset": -10_000,
    "rpm": 200,
    "tpm": 1_000_000,
    "free_rpm": 20,
    "free_tpm": 100_000,
    "anonymous_enabled_paid": False,
    "anonymous_enabled_free": True,
    "quota_reserve_tokens": 4000,
}


def test_generate_configs_respects_tier():
    """Premium OR models opt into the router pool; free OR models stay out.

    Strategy-3 split: premium participates in LiteLLM Router load balancing,
    free stays excluded because OpenRouter enforces a shared global free-tier
    bucket that per-deployment router accounting can't represent.
    """
    raw = [
        _minimal_openrouter_model(model_id="openai/gpt-4o"),
        _minimal_openrouter_model(
            model_id="meta-llama/llama-3.3-70b-instruct:free",
            pricing={"prompt": "0", "completion": "0"},
        ),
    ]
    cfgs = _generate_configs(raw, dict(_SETTINGS_BASE))
    by_model = {c["model_name"]: c for c in cfgs}

    paid = by_model["openai/gpt-4o"]
    assert paid["billing_tier"] == "premium"
    assert paid["rpm"] == 200
    assert paid["tpm"] == 1_000_000
    assert paid["anonymous_enabled"] is False
    assert paid["router_pool_eligible"] is True
    assert paid[_OPENROUTER_DYNAMIC_MARKER] is True

    free = by_model["meta-llama/llama-3.3-70b-instruct:free"]
    assert free["billing_tier"] == "free"
    assert free["rpm"] == 20
    assert free["tpm"] == 100_000
    assert free["anonymous_enabled"] is True
    assert free["router_pool_eligible"] is False


def test_generate_configs_excludes_upstream_openrouter_free_router():
    """OpenRouter's own ``openrouter/free`` meta-router must never become a card.

    The upstream API returns this as a first-class zero-priced model, so
    without an explicit blocklist entry it would slip through every other
    filter (text output, tool calling, 200k context, non-Amazon) and land
    in the selector as a duplicate of the concrete ``:free`` cards. The
    exclusion in ``_EXCLUDED_MODEL_IDS`` prevents that.
    """
    raw = [
        _minimal_openrouter_model(model_id="openai/gpt-4o"),
        _minimal_openrouter_model(
            model_id="openrouter/free",
            pricing={"prompt": "0", "completion": "0"},
        ),
    ]
    cfgs = _generate_configs(raw, dict(_SETTINGS_BASE))
    model_names = {c["model_name"] for c in cfgs}
    assert "openrouter/free" not in model_names
    assert "openai/gpt-4o" in model_names


def test_generate_configs_drops_non_text_and_non_tool_models():
    raw = [
        _minimal_openrouter_model(model_id="openai/gpt-4o"),
        {  # image-output model
            "id": "openai/dall-e",
            "architecture": {"output_modalities": ["image"]},
            "supported_parameters": ["tools"],
            "context_length": 200_000,
            "pricing": {"prompt": "0.01", "completion": "0.01"},
        },
        {  # text but no tool calling
            "id": "openai/completion-only",
            "architecture": {"output_modalities": ["text"]},
            "supported_parameters": [],
            "context_length": 200_000,
            "pricing": {"prompt": "0.01", "completion": "0.01"},
        },
    ]
    cfgs = _generate_configs(raw, dict(_SETTINGS_BASE))
    model_names = [c["model_name"] for c in cfgs]
    assert "openai/gpt-4o" in model_names
    assert "openai/dall-e" not in model_names
    assert "openai/completion-only" not in model_names


