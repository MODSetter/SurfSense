"""Unit tests for the chat-catalog ``supports_image_input`` capability flag.

Capability is sourced from two places, in order of preference:

1. ``architecture.input_modalities`` for dynamic OpenRouter chat configs
   (authoritative — OpenRouter publishes per-model modalities directly).
2. LiteLLM's authoritative model map (``litellm.supports_vision``) for
   YAML / BYOK configs that don't carry an explicit operator override.

The catalog default is *True* (conservative-allow): an unknown / unmapped
model is not pre-judged. The streaming-task safety net
(``is_known_text_only_chat_model``) is the only place a False actually
blocks a request — and it requires LiteLLM to *explicitly* mark the model
as text-only.
"""

from __future__ import annotations

import pytest

from app.services.openrouter_integration_service import (
    _OPENROUTER_DYNAMIC_MARKER,
    _generate_configs,
    _supports_image_input,
)

pytestmark = pytest.mark.unit


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


# ---------------------------------------------------------------------------
# _supports_image_input helper (OpenRouter modalities)
# ---------------------------------------------------------------------------


def test_supports_image_input_true_for_multimodal():
    assert (
        _supports_image_input(
            {
                "id": "openai/gpt-4o",
                "architecture": {
                    "input_modalities": ["text", "image"],
                    "output_modalities": ["text"],
                },
            }
        )
        is True
    )


def test_supports_image_input_false_for_text_only():
    """The exact failure mode the safety net guards against — DeepSeek V3
    is a text-in/text-out model and would 404 if forwarded image_url."""
    assert (
        _supports_image_input(
            {
                "id": "deepseek/deepseek-v3.2-exp",
                "architecture": {
                    "input_modalities": ["text"],
                    "output_modalities": ["text"],
                },
            }
        )
        is False
    )


def test_supports_image_input_false_when_modalities_missing():
    """Defensive: missing architecture is treated as text-only at the
    OpenRouter helper level. The wider catalog resolver
    (`derive_supports_image_input`) only consults modalities when they
    are non-empty, otherwise it falls back to LiteLLM."""
    assert _supports_image_input({"id": "weird/model"}) is False
    assert _supports_image_input({"id": "weird/model", "architecture": {}}) is False
    assert (
        _supports_image_input(
            {"id": "weird/model", "architecture": {"input_modalities": None}}
        )
        is False
    )


# ---------------------------------------------------------------------------
# _generate_configs threads the flag onto every emitted chat config
# ---------------------------------------------------------------------------


def test_generate_configs_emits_supports_image_input():
    raw = [
        {
            "id": "openai/gpt-4o",
            "architecture": {
                "input_modalities": ["text", "image"],
                "output_modalities": ["text"],
            },
            "supported_parameters": ["tools"],
            "context_length": 200_000,
            "pricing": {"prompt": "0.000005", "completion": "0.000015"},
        },
        {
            "id": "deepseek/deepseek-v3.2-exp",
            "architecture": {
                "input_modalities": ["text"],
                "output_modalities": ["text"],
            },
            "supported_parameters": ["tools"],
            "context_length": 200_000,
            "pricing": {"prompt": "0.000003", "completion": "0.000015"},
        },
    ]
    cfgs = _generate_configs(raw, dict(_SETTINGS_BASE))
    by_model = {c["model_name"]: c for c in cfgs}

    gpt = by_model["openai/gpt-4o"]
    assert gpt["supports_image_input"] is True
    assert gpt[_OPENROUTER_DYNAMIC_MARKER] is True

    deepseek = by_model["deepseek/deepseek-v3.2-exp"]
    assert deepseek["supports_image_input"] is False
    assert deepseek[_OPENROUTER_DYNAMIC_MARKER] is True


# ---------------------------------------------------------------------------
# YAML loader: defer to derive_supports_image_input on unannotated entries
# ---------------------------------------------------------------------------


def test_yaml_loader_resolves_unannotated_vision_model_to_true(tmp_path, monkeypatch):
    """The regression case: an Azure GPT-5.x YAML entry without a
    ``supports_image_input`` override should resolve to True via LiteLLM's
    model map (which says ``supports_vision: true``). Previously this
    defaulted to False, blocking every image turn for vision-capable
    YAML configs."""
    yaml_dir = tmp_path / "app" / "config"
    yaml_dir.mkdir(parents=True)
    (yaml_dir / "global_llm_config.yaml").write_text(
        """
global_llm_configs:
  - id: -2
    name: Azure GPT-4o
    provider: AZURE_OPENAI
    model_name: gpt-4o
    api_key: sk-test
""",
        encoding="utf-8",
    )

    from app import config as config_module

    monkeypatch.setattr(config_module, "BASE_DIR", tmp_path)

    configs = config_module.load_global_llm_configs()
    assert len(configs) == 1
    assert configs[0]["supports_image_input"] is True


def test_yaml_loader_respects_explicit_supports_image_input(tmp_path, monkeypatch):
    yaml_dir = tmp_path / "app" / "config"
    yaml_dir.mkdir(parents=True)
    (yaml_dir / "global_llm_config.yaml").write_text(
        """
global_llm_configs:
  - id: -1
    name: GPT-4o
    provider: OPENAI
    model_name: gpt-4o
    api_key: sk-test
    supports_image_input: false
""",
        encoding="utf-8",
    )

    from app import config as config_module

    monkeypatch.setattr(config_module, "BASE_DIR", tmp_path)

    configs = config_module.load_global_llm_configs()
    assert len(configs) == 1
    # Operator override always wins, even against LiteLLM's True.
    assert configs[0]["supports_image_input"] is False


def test_yaml_loader_unknown_model_default_allows(tmp_path, monkeypatch):
    """Unknown / unmapped model in YAML: default-allow. The streaming
    safety net (which requires an explicit-False from LiteLLM) is the
    only place a real block happens, so we don't lock the user out of
    a freshly added third-party entry the catalog can't introspect."""
    yaml_dir = tmp_path / "app" / "config"
    yaml_dir.mkdir(parents=True)
    (yaml_dir / "global_llm_config.yaml").write_text(
        """
global_llm_configs:
  - id: -1
    name: Some Brand New Model
    provider: CUSTOM
    custom_provider: brand_new_proxy
    model_name: brand-new-model-x9
    api_key: sk-test
""",
        encoding="utf-8",
    )

    from app import config as config_module

    monkeypatch.setattr(config_module, "BASE_DIR", tmp_path)

    configs = config_module.load_global_llm_configs()
    assert len(configs) == 1
    assert configs[0]["supports_image_input"] is True


# ---------------------------------------------------------------------------
# AgentConfig threads the flag through both YAML and Auto / BYOK
# ---------------------------------------------------------------------------


def test_agent_config_from_yaml_explicit_overrides_resolver():
    from app.agents.new_chat.llm_config import AgentConfig

    cfg_text_only = AgentConfig.from_yaml_config(
        {
            "id": -1,
            "name": "Text Only Override",
            "provider": "openai",
            "model_name": "gpt-4o",  # Capable per LiteLLM, but operator says no.
            "api_key": "sk-test",
            "supports_image_input": False,
        }
    )
    cfg_explicit_vision = AgentConfig.from_yaml_config(
        {
            "id": -2,
            "name": "GPT-4o",
            "provider": "openai",
            "model_name": "gpt-4o",
            "api_key": "sk-test",
            "supports_image_input": True,
        }
    )
    assert cfg_text_only.supports_image_input is False
    assert cfg_explicit_vision.supports_image_input is True


def test_agent_config_from_yaml_unannotated_uses_resolver():
    """Without an explicit YAML key, AgentConfig defers to the catalog
    resolver — for ``gpt-4o`` LiteLLM's map says supports_vision=True."""
    from app.agents.new_chat.llm_config import AgentConfig

    cfg = AgentConfig.from_yaml_config(
        {
            "id": -1,
            "name": "GPT-4o (no override)",
            "provider": "openai",
            "model_name": "gpt-4o",
            "api_key": "sk-test",
        }
    )
    assert cfg.supports_image_input is True


def test_agent_config_auto_mode_supports_image_input():
    """Auto routes across the pool. We optimistically allow image input
    so users can keep their selection on Auto with a vision-capable
    deployment somewhere in the pool. The router's own `allowed_fails`
    handles non-vision deployments via fallback."""
    from app.agents.new_chat.llm_config import AgentConfig

    auto = AgentConfig.from_auto_mode()
    assert auto.supports_image_input is True
