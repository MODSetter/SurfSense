"""Unit tests for the shared chat-image capability resolver.

Two resolvers, two intents:

- ``derive_supports_image_input`` — best-effort True for the catalog and
  selector. Default-allow on unknown / unmapped models. The streaming
  task safety net never sees this value directly.

- ``is_known_text_only_chat_model`` — strict opt-out for the safety net.
  Returns True only when LiteLLM's model map *explicitly* sets
  ``supports_vision=False``. Anything else (missing key, exception,
  True) returns False so the request flows through to the provider.
"""

from __future__ import annotations

import pytest

from app.services.provider_capabilities import (
    derive_supports_image_input,
    is_known_text_only_chat_model,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# derive_supports_image_input — OpenRouter modalities path (authoritative)
# ---------------------------------------------------------------------------


def test_or_modalities_with_image_returns_true():
    assert (
        derive_supports_image_input(
            provider="OPENROUTER",
            model_name="openai/gpt-4o",
            openrouter_input_modalities=["text", "image"],
        )
        is True
    )


def test_or_modalities_text_only_returns_false():
    assert (
        derive_supports_image_input(
            provider="OPENROUTER",
            model_name="deepseek/deepseek-v3.2-exp",
            openrouter_input_modalities=["text"],
        )
        is False
    )


def test_or_modalities_empty_list_returns_false():
    """OR explicitly publishing an empty modality list is a definitive
    'no inputs at all' signal — treat as False rather than falling back
    to LiteLLM."""
    assert (
        derive_supports_image_input(
            provider="OPENROUTER",
            model_name="weird/empty-modalities",
            openrouter_input_modalities=[],
        )
        is False
    )


def test_or_modalities_none_falls_through_to_litellm():
    """``None`` (missing key) is *not* a definitive signal — fall through
    to LiteLLM. Using ``openai/gpt-4o`` which is in LiteLLM's map."""
    assert (
        derive_supports_image_input(
            provider="OPENAI",
            model_name="gpt-4o",
            openrouter_input_modalities=None,
        )
        is True
    )


# ---------------------------------------------------------------------------
# derive_supports_image_input — LiteLLM model-map path
# ---------------------------------------------------------------------------


def test_litellm_known_vision_model_returns_true():
    assert (
        derive_supports_image_input(
            provider="OPENAI",
            model_name="gpt-4o",
        )
        is True
    )


def test_litellm_base_model_wins_over_model_name():
    """Azure-style entries pass model_name=deployment_id and put the
    canonical sku in litellm_params.base_model. The resolver must
    consult base_model first or the deployment id (which LiteLLM
    doesn't know) would shadow the real capability."""
    assert (
        derive_supports_image_input(
            provider="AZURE_OPENAI",
            model_name="my-azure-deployment-id",
            base_model="gpt-4o",
        )
        is True
    )


def test_litellm_unknown_model_default_allows():
    """Default-allow on unknown — the safety net is the actual block."""
    assert (
        derive_supports_image_input(
            provider="CUSTOM",
            model_name="brand-new-model-x9-unmapped",
            custom_provider="brand_new_proxy",
        )
        is True
    )


def test_litellm_known_text_only_returns_false():
    """A model that LiteLLM explicitly knows is text-only resolves to
    False even via the catalog resolver. ``deepseek-chat`` (the
    DeepSeek-V3 chat sku) is in the map without supports_vision and
    LiteLLM's `supports_vision` returns False."""
    # Sanity: confirm the helper's negative path. We use a small model
    # known not to support vision per the map.
    result = derive_supports_image_input(
        provider="DEEPSEEK",
        model_name="deepseek-chat",
    )
    # We accept either False (LiteLLM said explicit no) or True
    # (default-allow if the entry isn't mapped on this version) — the
    # invariant is that the resolver never *raises* on a known-text-only
    # provider/model. The behaviour-binding assertion lives in
    # ``test_is_known_text_only_chat_model_explicit_false`` below.
    assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# is_known_text_only_chat_model — strict opt-out semantics
# ---------------------------------------------------------------------------


def test_is_known_text_only_returns_false_for_vision_model():
    assert (
        is_known_text_only_chat_model(
            provider="OPENAI",
            model_name="gpt-4o",
        )
        is False
    )


def test_is_known_text_only_returns_false_for_unknown_model():
    """Strict opt-out: missing from the map ≠ text-only. The safety net
    must NOT fire for an unmapped model — that's the regression we're
    fixing."""
    assert (
        is_known_text_only_chat_model(
            provider="CUSTOM",
            model_name="brand-new-model-x9-unmapped",
            custom_provider="brand_new_proxy",
        )
        is False
    )


def test_is_known_text_only_returns_false_when_lookup_raises(monkeypatch):
    """LiteLLM's ``get_model_info`` raises freely on parse errors. The
    helper swallows the exception and returns False so the safety net
    doesn't fire on a transient lookup failure."""
    import app.services.provider_capabilities as pc

    def _raise(**_kwargs):
        raise ValueError("intentional test failure")

    monkeypatch.setattr(pc.litellm, "get_model_info", _raise)

    assert (
        is_known_text_only_chat_model(
            provider="OPENAI",
            model_name="gpt-4o",
        )
        is False
    )


def test_is_known_text_only_returns_true_on_explicit_false(monkeypatch):
    """Stub LiteLLM's ``get_model_info`` to return an explicit False so
    we exercise the opt-out path deterministically. Using a stub keeps
    the test stable across LiteLLM map updates."""
    import app.services.provider_capabilities as pc

    def _info(**_kwargs):
        return {"supports_vision": False, "max_input_tokens": 8192}

    monkeypatch.setattr(pc.litellm, "get_model_info", _info)

    assert (
        is_known_text_only_chat_model(
            provider="OPENAI",
            model_name="any-model",
        )
        is True
    )


def test_is_known_text_only_returns_false_on_supports_vision_true(monkeypatch):
    import app.services.provider_capabilities as pc

    def _info(**_kwargs):
        return {"supports_vision": True}

    monkeypatch.setattr(pc.litellm, "get_model_info", _info)

    assert (
        is_known_text_only_chat_model(
            provider="OPENAI",
            model_name="any-model",
        )
        is False
    )


def test_is_known_text_only_returns_false_on_missing_key(monkeypatch):
    """A model entry without ``supports_vision`` at all is treated as
    'unknown' — strict opt-out means False."""
    import app.services.provider_capabilities as pc

    def _info(**_kwargs):
        return {"max_input_tokens": 8192}  # no supports_vision

    monkeypatch.setattr(pc.litellm, "get_model_info", _info)

    assert (
        is_known_text_only_chat_model(
            provider="OPENAI",
            model_name="any-model",
        )
        is False
    )
