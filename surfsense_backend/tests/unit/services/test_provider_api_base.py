"""Unit tests for the shared ``api_base`` resolver.

The cascade exists so vision and image-gen call sites can't silently
inherit ``litellm.api_base`` (commonly set by ``AZURE_OPENAI_ENDPOINT``)
when an OpenRouter / Groq / etc. config ships an empty string. See
``provider_api_base`` module docstring for the original repro
(OpenRouter image-gen 404-ing against an Azure endpoint).
"""

from __future__ import annotations

import pytest

from app.services.provider_api_base import (
    PROVIDER_DEFAULT_API_BASE,
    PROVIDER_KEY_DEFAULT_API_BASE,
    resolve_api_base,
)

pytestmark = pytest.mark.unit


def test_config_value_wins_over_defaults():
    """A non-empty config value is always returned verbatim, even when the
    provider has a default — the operator gets the last word."""
    result = resolve_api_base(
        provider="OPENROUTER",
        provider_prefix="openrouter",
        config_api_base="https://my-openrouter-mirror.example.com/v1",
    )
    assert result == "https://my-openrouter-mirror.example.com/v1"


def test_provider_key_default_when_config_missing():
    """``DEEPSEEK`` shares the ``openai`` LiteLLM prefix but has its own
    base URL — the provider-key map must take precedence over the prefix
    map so DeepSeek requests don't go to OpenAI."""
    result = resolve_api_base(
        provider="DEEPSEEK",
        provider_prefix="openai",
        config_api_base=None,
    )
    assert result == PROVIDER_KEY_DEFAULT_API_BASE["DEEPSEEK"]


def test_provider_prefix_default_when_no_key_default():
    result = resolve_api_base(
        provider="OPENROUTER",
        provider_prefix="openrouter",
        config_api_base=None,
    )
    assert result == PROVIDER_DEFAULT_API_BASE["openrouter"]


def test_unknown_provider_returns_none():
    """When neither map matches we return ``None`` so the caller can let
    LiteLLM apply its own provider-integration default (Azure deployment
    URL, custom-provider URL, etc.)."""
    result = resolve_api_base(
        provider="SOMETHING_NEW",
        provider_prefix="something_new",
        config_api_base=None,
    )
    assert result is None


def test_empty_string_config_treated_as_missing():
    """The original bug: OpenRouter dynamic configs ship ``api_base=""``
    and downstream call sites use ``if cfg.get("api_base"):`` — empty
    strings are falsy in Python but the cascade has to step in anyway."""
    result = resolve_api_base(
        provider="OPENROUTER",
        provider_prefix="openrouter",
        config_api_base="",
    )
    assert result == PROVIDER_DEFAULT_API_BASE["openrouter"]


def test_whitespace_only_config_treated_as_missing():
    """A config value of ``"   "`` is a configuration mistake — treat it
    as missing instead of forwarding whitespace to LiteLLM (which would
    almost certainly 404)."""
    result = resolve_api_base(
        provider="OPENROUTER",
        provider_prefix="openrouter",
        config_api_base="   ",
    )
    assert result == PROVIDER_DEFAULT_API_BASE["openrouter"]


def test_provider_case_insensitive():
    """Some call sites pass the provider lowercase (DB enum value), others
    uppercase (YAML key). Both must resolve."""
    upper = resolve_api_base(
        provider="DEEPSEEK", provider_prefix="openai", config_api_base=None
    )
    lower = resolve_api_base(
        provider="deepseek", provider_prefix="openai", config_api_base=None
    )
    assert upper == lower == PROVIDER_KEY_DEFAULT_API_BASE["DEEPSEEK"]


def test_all_inputs_none_returns_none():
    assert (
        resolve_api_base(provider=None, provider_prefix=None, config_api_base=None)
        is None
    )
