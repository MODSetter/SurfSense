"""Tests for ``_resolve_prompt_model_name`` in :mod:`app.agents.new_chat.chat_deepagent`.

The helper picks the model id fed to ``detect_provider_variant`` so the
right ``<provider_hints>`` block lands in the system prompt. The tests
below pin its preference order:

1. ``agent_config.litellm_params["base_model"]`` (Azure-correct).
2. ``agent_config.model_name``.
3. ``getattr(llm, "model", None)``.

Without (1) an Azure deployment named e.g. ``"prod-chat-001"`` would
silently miss every provider regex.
"""

from __future__ import annotations

import pytest

from app.agents.new_chat.chat_deepagent import _resolve_prompt_model_name
from app.agents.new_chat.llm_config import AgentConfig

pytestmark = pytest.mark.unit


def _make_cfg(**overrides) -> AgentConfig:
    """Build an ``AgentConfig`` with sensible defaults for the helper test."""
    defaults = {
        "provider": "OPENAI",
        "model_name": "x",
        "api_key": "k",
    }
    return AgentConfig(**{**defaults, **overrides})


class _FakeLLM:
    """Stand-in for a ``ChatLiteLLM`` / ``ChatLiteLLMRouter`` instance.

    The resolver only reads the ``.model`` attribute via ``getattr``,
    matching the established idiom in ``knowledge_search.py`` /
    ``stream_new_chat.py`` / ``document_summarizer.py``.
    """

    def __init__(self, model: str | None) -> None:
        self.model = model


def test_prefers_litellm_params_base_model_over_deployment_name() -> None:
    """Azure deployment slug must NOT shadow the underlying model family.

    This is the failure mode the helper exists to prevent: a deployment
    named ``"azure/prod-chat-001"`` would not match any provider regex
    on its own, but the family ``"gpt-4o"`` lives in
    ``litellm_params["base_model"]`` and routes to ``openai_classic``.
    """
    cfg = _make_cfg(
        model_name="azure/prod-chat-001",
        litellm_params={"base_model": "gpt-4o"},
    )
    assert _resolve_prompt_model_name(cfg, _FakeLLM("azure/prod-chat-001")) == "gpt-4o"


def test_falls_back_to_model_name_when_litellm_params_is_none() -> None:
    cfg = _make_cfg(
        model_name="anthropic/claude-3-5-sonnet",
        litellm_params=None,
    )
    got = _resolve_prompt_model_name(cfg, _FakeLLM("anthropic/claude-3-5-sonnet"))
    assert got == "anthropic/claude-3-5-sonnet"


def test_handles_litellm_params_without_base_model_key() -> None:
    cfg = _make_cfg(
        model_name="openai/gpt-4o",
        litellm_params={"temperature": 0.5},
    )
    assert _resolve_prompt_model_name(cfg, _FakeLLM("openai/gpt-4o")) == "openai/gpt-4o"


def test_ignores_blank_base_model() -> None:
    """Whitespace-only ``base_model`` must not shadow ``model_name``."""
    cfg = _make_cfg(
        model_name="openai/gpt-4o",
        litellm_params={"base_model": "   "},
    )
    assert _resolve_prompt_model_name(cfg, _FakeLLM("openai/gpt-4o")) == "openai/gpt-4o"


def test_ignores_non_string_base_model() -> None:
    """Defensive: a non-string ``base_model`` should not crash the resolver."""
    cfg = _make_cfg(
        model_name="openai/gpt-4o",
        litellm_params={"base_model": 42},
    )
    assert _resolve_prompt_model_name(cfg, _FakeLLM("openai/gpt-4o")) == "openai/gpt-4o"


def test_falls_back_to_llm_model_when_no_agent_config() -> None:
    """No ``agent_config`` -> use ``llm.model`` directly. Defensive path
    for direct callers; production callers always supply a config."""
    assert (
        _resolve_prompt_model_name(None, _FakeLLM("openai/gpt-4o-mini"))
        == "openai/gpt-4o-mini"
    )


def test_returns_none_when_nothing_available() -> None:
    """``compose_system_prompt`` treats ``None`` as the ``"default"``
    variant and emits no provider block."""
    assert _resolve_prompt_model_name(None, _FakeLLM(None)) is None


def test_auto_mode_resolves_to_auto_string() -> None:
    """Auto mode -> ``"auto"``. ``detect_provider_variant("auto")``
    returns ``"default"``, which is correct: the child model isn't
    known until the LiteLLM Router dispatches."""
    cfg = AgentConfig.from_auto_mode()
    assert _resolve_prompt_model_name(cfg, _FakeLLM("auto")) == "auto"
