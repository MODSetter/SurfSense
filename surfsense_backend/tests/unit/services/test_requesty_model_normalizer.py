"""Unit tests for Requesty model normalization.

Mirrors the OpenRouter normalizer coverage but exercises Requesty's flat
boolean capability fields (``supports_tool_calling`` / ``supports_vision``)
and ``context_window`` sizing.
"""

from __future__ import annotations

import pytest

from app.services.requesty_model_normalizer import (
    is_requesty_chat_model,
    is_requesty_image_model,
    normalize_requesty_models,
    supports_image_input,
    supports_tool_calling,
)

pytestmark = pytest.mark.unit


def _requesty_model(
    *,
    model_id: str,
    context_window: int = 128_000,
    tools: bool = True,
    vision: bool = False,
    image_generation: bool = False,
    name: str | None = None,
) -> dict:
    """Return a synthetic Requesty ``/v1/models`` entry.

    Only the fields the normalizer inspects are populated; the live payload
    carries many more (pricing, ``supports_caching``, ``description``, ...).
    """
    return {
        "id": model_id,
        "name": name or model_id,
        "api": "chat",
        "object": "model",
        "context_window": context_window,
        "supports_tool_calling": tools,
        "supports_vision": vision,
        "supports_image_generation": image_generation,
    }


def test_chat_model_requires_slash_tools_and_context():
    assert is_requesty_chat_model(_requesty_model(model_id="openai/gpt-4o-mini"))
    assert not is_requesty_chat_model(
        _requesty_model(model_id="openai/gpt-4o-mini", tools=False)
    )
    assert not is_requesty_chat_model(
        _requesty_model(model_id="openai/gpt-4o-mini", context_window=8_000)
    )
    assert not is_requesty_chat_model(_requesty_model(model_id="bare-model"))


def test_excluded_provider_slug_is_filtered():
    assert not is_requesty_chat_model(
        _requesty_model(model_id="amazon/nova-pro-v1")
    )


def test_image_generation_models_excluded_from_chat_and_flagged():
    image_model = _requesty_model(
        model_id="google/gemini-2.5-flash-image", image_generation=True
    )
    assert not is_requesty_chat_model(image_model)
    assert is_requesty_image_model(image_model)


def test_capability_helpers_read_flat_booleans():
    model = _requesty_model(
        model_id="anthropic/claude-sonnet-4-5", vision=True, tools=True
    )
    assert supports_image_input(model) is True
    assert supports_tool_calling(model) is True


def test_normalize_maps_context_window_and_capabilities():
    normalized = normalize_requesty_models(
        [
            _requesty_model(
                model_id="openai/gpt-4o-mini",
                context_window=128_000,
                vision=True,
                name="GPT-4o mini",
            ),
            _requesty_model(model_id="openai/gpt-4o-mini", tools=False),
            _requesty_model(
                model_id="black-forest-labs/flux", image_generation=True
            ),
        ]
    )

    assert len(normalized) == 1
    entry = normalized[0]
    assert entry["model_id"] == "openai/gpt-4o-mini"
    assert entry["display_name"] == "GPT-4o mini"
    assert entry["supports_chat"] is True
    assert entry["max_input_tokens"] == 128_000
    assert entry["supports_image_input"] is True
    assert entry["supports_tools"] is True
    assert entry["supports_image_generation"] is False
    assert entry["metadata"]["id"] == "openai/gpt-4o-mini"
