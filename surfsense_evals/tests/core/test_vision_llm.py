"""Tests for vision LLM auto-pick + explicit-slug resolution."""

from __future__ import annotations

import pytest

from surfsense_evals.core.clients.search_space import VisionLlmConfigEntry
from surfsense_evals.core.vision_llm import (
    RECOMMENDED_VISION_PRIORITY,
    VisionConfigError,
    resolve_vision_llm,
)


def _entry(*, id: int, model_name: str, provider: str = "OPENROUTER") -> VisionLlmConfigEntry:
    return VisionLlmConfigEntry(
        id=id,
        name=f"OpenRouter • {model_name}",
        provider=provider,
        model_name=model_name,
        is_auto_mode=False,
        raw={},
    )


# ---------------------------------------------------------------------------
# Explicit slug resolution
# ---------------------------------------------------------------------------


def test_explicit_slug_resolves_to_matching_config_id():
    candidates = [
        _entry(id=-101, model_name="anthropic/claude-sonnet-4.5"),
        _entry(id=-102, model_name="openai/gpt-5"),
    ]
    resolved = resolve_vision_llm(candidates, explicit_slug="openai/gpt-5")
    assert resolved.config_id == -102
    assert resolved.provider_model == "openai/gpt-5"
    assert resolved.selected_via == "explicit"


def test_explicit_slug_with_no_match_raises_with_helpful_listing():
    candidates = [_entry(id=-101, model_name="anthropic/claude-sonnet-4.5")]
    with pytest.raises(VisionConfigError) as exc_info:
        resolve_vision_llm(candidates, explicit_slug="some/missing-slug")
    msg = str(exc_info.value)
    assert "some/missing-slug" in msg
    assert "anthropic/claude-sonnet-4.5" in msg  # surfaced as a sample


def test_explicit_slug_skips_non_openrouter_entries():
    """A YAML BYOK entry with a colliding model_name shouldn't accidentally match."""

    candidates = [
        _entry(id=42, model_name="openai/gpt-5", provider="OPENAI"),
        _entry(id=-101, model_name="openai/gpt-5"),
    ]
    resolved = resolve_vision_llm(candidates, explicit_slug="openai/gpt-5")
    assert resolved.config_id == -101  # the OpenRouter one, not the BYOK one


# ---------------------------------------------------------------------------
# Auto-pick by recommended priority
# ---------------------------------------------------------------------------


def test_auto_pick_walks_priority_list_in_order():
    candidates = [
        _entry(id=-300, model_name="google/gemini-2.5-pro"),
        _entry(id=-200, model_name="anthropic/claude-opus-4.7"),
        _entry(id=-100, model_name="anthropic/claude-sonnet-4.5"),
    ]
    resolved = resolve_vision_llm(candidates, explicit_slug=None)
    # claude-sonnet-4.5 is first in the priority tuple, so it wins.
    assert resolved.config_id == -100
    assert resolved.provider_model == "anthropic/claude-sonnet-4.5"
    assert resolved.selected_via == "auto-priority"


def test_auto_pick_skips_to_next_priority_when_first_unavailable():
    candidates = [
        _entry(id=-200, model_name="anthropic/claude-opus-4.7"),
        _entry(id=-300, model_name="google/gemini-2.5-pro"),
    ]
    resolved = resolve_vision_llm(candidates, explicit_slug=None)
    # claude-sonnet-4.5 not registered → claude-opus-4.7 is next in priority.
    assert resolved.provider_model == "anthropic/claude-opus-4.7"
    assert resolved.selected_via == "auto-priority"


def test_auto_pick_falls_back_to_first_openrouter_when_no_recommended_match():
    candidates = [
        _entry(id=-700, model_name="some/exotic-vision-model"),
        _entry(id=-800, model_name="another/exotic-vision-model"),
    ]
    resolved = resolve_vision_llm(candidates, explicit_slug=None)
    # Neither matches the priority list → first OpenRouter entry wins.
    assert resolved.config_id == -700
    assert resolved.selected_via == "auto-fallback"


def test_auto_pick_with_zero_openrouter_candidates_raises():
    candidates: list[VisionLlmConfigEntry] = []
    with pytest.raises(VisionConfigError) as exc_info:
        resolve_vision_llm(candidates, explicit_slug=None)
    assert "vision_enabled: true" in str(exc_info.value)


def test_auto_pick_ignores_non_openrouter_entries():
    candidates = [
        _entry(id=99, model_name="anthropic/claude-sonnet-4.5", provider="ANTHROPIC"),
    ]
    with pytest.raises(VisionConfigError):
        resolve_vision_llm(candidates, explicit_slug=None)


def test_recommended_priority_is_a_stable_public_list():
    """If you reorder this, update the README's auto-pick claim too."""

    assert RECOMMENDED_VISION_PRIORITY[0] == "anthropic/claude-sonnet-4.5"
    assert "google/gemini-2.5-pro" in RECOMMENDED_VISION_PRIORITY
