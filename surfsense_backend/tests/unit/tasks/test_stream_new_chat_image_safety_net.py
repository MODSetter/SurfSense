"""Predicate-level test for the chat streaming safety net.

The safety net in ``stream_new_chat`` rejects an image turn early with
a friendly ``MODEL_DOES_NOT_SUPPORT_IMAGE_INPUT`` SSE error when the
selected model is *known* to be text-only. The earlier round of this
work used a strict opt-in flag (``supports_image_input`` defaulting to
False on every YAML entry) which blocked vision-capable Azure GPT-5.x
deployments — this is the regression we're fixing.

The new predicate is :func:`is_known_text_only_chat_model`, which
returns True only when LiteLLM's authoritative model map *explicitly*
sets ``supports_vision=False``. Anything else (vision True, missing
key, exception) returns False so the request flows through to the
provider.

We exercise the predicate directly here rather than driving the full
``stream_new_chat`` generator — covering the gate in isolation keeps
the test focused on the regression while the generator's wider behavior
is exercised by the integration suite.
"""

from __future__ import annotations

import pytest

from app.services.provider_capabilities import is_known_text_only_chat_model

pytestmark = pytest.mark.unit


def test_safety_net_does_not_fire_for_azure_gpt_4o():
    """Regression: ``azure/gpt-4o`` (and the GPT-5.x variants) is
    vision-capable per LiteLLM's model map. The previous round's
    blanket-False default blocked it; the new predicate must NOT mark
    it text-only."""
    assert (
        is_known_text_only_chat_model(
            provider="AZURE_OPENAI",
            model_name="my-azure-deployment",
            base_model="gpt-4o",
        )
        is False
    )


def test_safety_net_does_not_fire_for_unknown_model():
    """Default-pass on unknown — the safety net only blocks definitive
    text-only confirmations. A freshly added third-party model that
    LiteLLM doesn't know about must flow through to the provider."""
    assert (
        is_known_text_only_chat_model(
            provider="CUSTOM",
            custom_provider="brand_new_proxy",
            model_name="brand-new-model-x9",
        )
        is False
    )


def test_safety_net_does_not_fire_when_lookup_raises(monkeypatch):
    """Transient ``litellm.get_model_info`` exception ≠ block. The
    helper swallows the error and treats it as 'unknown' → False."""
    import app.services.provider_capabilities as pc

    def _raise(**_kwargs):
        raise RuntimeError("intentional test failure")

    monkeypatch.setattr(pc.litellm, "get_model_info", _raise)

    assert (
        is_known_text_only_chat_model(
            provider="OPENAI",
            model_name="gpt-4o",
        )
        is False
    )


def test_safety_net_fires_only_on_explicit_false(monkeypatch):
    """Stub LiteLLM to assert the only path that returns True is the
    explicit ``supports_vision=False`` case. Anything else (True,
    None, missing key) returns False from the predicate."""
    import app.services.provider_capabilities as pc

    def _info_explicit_false(**_kwargs):
        return {"supports_vision": False, "max_input_tokens": 8192}

    monkeypatch.setattr(pc.litellm, "get_model_info", _info_explicit_false)
    assert (
        is_known_text_only_chat_model(
            provider="OPENAI",
            model_name="text-only-stub",
        )
        is True
    )

    def _info_true(**_kwargs):
        return {"supports_vision": True}

    monkeypatch.setattr(pc.litellm, "get_model_info", _info_true)
    assert (
        is_known_text_only_chat_model(
            provider="OPENAI",
            model_name="vision-stub",
        )
        is False
    )

    def _info_missing(**_kwargs):
        return {"max_input_tokens": 8192}

    monkeypatch.setattr(pc.litellm, "get_model_info", _info_missing)
    assert (
        is_known_text_only_chat_model(
            provider="OPENAI",
            model_name="missing-key-stub",
        )
        is False
    )
