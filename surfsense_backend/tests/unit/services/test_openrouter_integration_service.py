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


# ---------------------------------------------------------------------------
# _generate_image_gen_configs / _generate_vision_llm_configs
# ---------------------------------------------------------------------------


def test_generate_image_gen_configs_filters_by_image_output():
    """Only models with ``output_modalities`` containing ``image`` are emitted.
    Tool-calling and context filters are intentionally NOT applied — image
    generation has nothing to do with tool calls and context windows.
    """
    from app.services.openrouter_integration_service import (
        _generate_image_gen_configs,
    )

    raw = [
        # Pure image-gen model (small context, no tools — should still emit).
        {
            "id": "openai/gpt-image-1",
            "architecture": {"output_modalities": ["image"]},
            "context_length": 4_000,
            "pricing": {"prompt": "0", "completion": "0"},
        },
        # Multi-modal: text+image output (should still emit).
        {
            "id": "google/gemini-2.5-flash-image",
            "architecture": {"output_modalities": ["text", "image"]},
            "context_length": 1_000_000,
            "pricing": {"prompt": "0.000001", "completion": "0.000004"},
        },
        # Pure text model — must NOT emit.
        {
            "id": "openai/gpt-4o",
            "architecture": {"output_modalities": ["text"]},
            "context_length": 128_000,
            "pricing": {"prompt": "0.000005", "completion": "0.000015"},
        },
    ]

    cfgs = _generate_image_gen_configs(raw, dict(_SETTINGS_BASE))
    model_names = {c["model_name"] for c in cfgs}
    assert "openai/gpt-image-1" in model_names
    assert "google/gemini-2.5-flash-image" in model_names
    assert "openai/gpt-4o" not in model_names

    # Each config must carry ``billing_tier`` for routing in image_generation_routes.
    for c in cfgs:
        assert c["billing_tier"] in {"free", "premium"}
        assert c["provider"] == "OPENROUTER"
        assert c[_OPENROUTER_DYNAMIC_MARKER] is True


def test_generate_image_gen_configs_assigns_image_id_offset():
    """Image configs use a different id_offset (-20000) so their negative
    IDs don't collide with chat configs (-10000) or vision configs (-30000).
    """
    from app.services.openrouter_integration_service import (
        _generate_image_gen_configs,
    )

    raw = [
        {
            "id": "openai/gpt-image-1",
            "architecture": {"output_modalities": ["image"]},
            "context_length": 4_000,
            "pricing": {"prompt": "0", "completion": "0"},
        }
    ]
    # Don't pass image_id_offset → use the module default (-20000).
    cfgs = _generate_image_gen_configs(raw, dict(_SETTINGS_BASE))
    assert all(c["id"] < -20_000 + 1 for c in cfgs)
    assert all(c["id"] > -29_000_000 for c in cfgs)


def test_generate_vision_llm_configs_filters_by_image_input_text_output():
    """Vision LLMs must accept image input AND emit text — pure image-gen
    (no text out) and text-only (no image in) models are excluded.
    """
    from app.services.openrouter_integration_service import (
        _generate_vision_llm_configs,
    )

    raw = [
        # GPT-4o: vision LLM (image in, text out) — must emit.
        {
            "id": "openai/gpt-4o",
            "architecture": {
                "input_modalities": ["text", "image"],
                "output_modalities": ["text"],
            },
            "context_length": 128_000,
            "pricing": {"prompt": "0.000005", "completion": "0.000015"},
        },
        # Pure image generator — image *output*, no text out. Must NOT emit.
        {
            "id": "openai/gpt-image-1",
            "architecture": {
                "input_modalities": ["text"],
                "output_modalities": ["image"],
            },
            "context_length": 4_000,
            "pricing": {"prompt": "0", "completion": "0"},
        },
        # Pure text model (no image in). Must NOT emit.
        {
            "id": "anthropic/claude-3-haiku",
            "architecture": {
                "input_modalities": ["text"],
                "output_modalities": ["text"],
            },
            "context_length": 200_000,
            "pricing": {"prompt": "0.000001", "completion": "0.000005"},
        },
    ]

    cfgs = _generate_vision_llm_configs(raw, dict(_SETTINGS_BASE))
    names = {c["model_name"] for c in cfgs}
    assert names == {"openai/gpt-4o"}

    cfg = cfgs[0]
    assert cfg["billing_tier"] == "premium"
    # Pricing carried inline so pricing_registration can register vision
    # under ``openrouter/openai/gpt-4o`` even if the chat catalogue cache
    # is cleared.
    assert cfg["input_cost_per_token"] == pytest.approx(5e-6)
    assert cfg["output_cost_per_token"] == pytest.approx(15e-6)
    assert cfg[_OPENROUTER_DYNAMIC_MARKER] is True


def test_generate_vision_llm_configs_drops_chat_only_filters():
    """A small-context vision model that doesn't advertise tool calling is
    still a valid vision LLM for "describe this image" prompts. The chat
    filters (``supports_tool_calling``, ``has_sufficient_context``) must
    NOT be applied to vision emission.
    """
    from app.services.openrouter_integration_service import (
        _generate_vision_llm_configs,
    )

    raw = [
        {
            "id": "tiny/vision-mini",
            "architecture": {
                "input_modalities": ["text", "image"],
                "output_modalities": ["text"],
            },
            "supported_parameters": [],  # no tools
            "context_length": 4_000,  # well below MIN_CONTEXT_LENGTH
            "pricing": {"prompt": "0.0000001", "completion": "0.0000005"},
        }
    ]

    cfgs = _generate_vision_llm_configs(raw, dict(_SETTINGS_BASE))
    assert len(cfgs) == 1
    assert cfgs[0]["model_name"] == "tiny/vision-mini"
