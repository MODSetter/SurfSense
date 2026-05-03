"""Unit tests for ``supports_image_input`` derivation on the chat global
config endpoint (``GET /global-new-llm-configs``).

Resolution order (matches ``new_llm_config_routes.get_global_new_llm_configs``):

1. Explicit ``supports_image_input`` on the cfg dict (set by the YAML
   loader for operator overrides, or by the OpenRouter integration from
   ``architecture.input_modalities``) — wins.
2. ``derive_supports_image_input`` helper — default-allow on unknown
   models, only False when LiteLLM / OR modalities are definitive.

The flag is purely informational at the API boundary. The streaming
task safety net (``is_known_text_only_chat_model``) is the actual block,
and it requires LiteLLM to *explicitly* mark the model as text-only.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


_FIXTURE: list[dict] = [
    {
        "id": -1,
        "name": "GPT-4o (explicit true)",
        "description": "vision-capable, explicit YAML override",
        "provider": "OPENAI",
        "model_name": "gpt-4o",
        "api_key": "sk-test",
        "billing_tier": "free",
        "supports_image_input": True,
    },
    {
        "id": -2,
        "name": "DeepSeek V3 (explicit false)",
        "description": "OpenRouter dynamic — modality-derived false",
        "provider": "OPENROUTER",
        "model_name": "deepseek/deepseek-v3.2-exp",
        "api_key": "sk-or-test",
        "api_base": "https://openrouter.ai/api/v1",
        "billing_tier": "free",
        "supports_image_input": False,
    },
    {
        "id": -10_010,
        "name": "Unannotated GPT-4o",
        "description": "no flag set — resolver should derive True via LiteLLM",
        "provider": "OPENAI",
        "model_name": "gpt-4o",
        "api_key": "sk-test",
        "billing_tier": "free",
        # supports_image_input intentionally absent
    },
    {
        "id": -10_011,
        "name": "Unannotated unknown model",
        "description": "unmapped — default-allow True",
        "provider": "CUSTOM",
        "custom_provider": "brand_new_proxy",
        "model_name": "brand-new-model-x9",
        "api_key": "sk-test",
        "billing_tier": "free",
    },
]


@pytest.mark.asyncio
async def test_global_new_llm_configs_emit_supports_image_input(monkeypatch):
    """Each emitted chat config carries ``supports_image_input`` as a
    bool. Explicit values win; unannotated entries are resolved via the
    helper (default-allow True)."""
    from app.config import config
    from app.routes import new_llm_config_routes

    monkeypatch.setattr(config, "GLOBAL_LLM_CONFIGS", _FIXTURE, raising=False)

    payload = await new_llm_config_routes.get_global_new_llm_configs(user=None)
    by_id = {c["id"]: c for c in payload}

    # Auto stub: optimistic True so the user can keep Auto selected with
    # vision-capable deployments somewhere in the pool.
    assert 0 in by_id, "Auto stub should be emitted when configs exist"
    assert by_id[0]["supports_image_input"] is True
    assert by_id[0]["is_auto_mode"] is True

    # Explicit True is preserved.
    assert by_id[-1]["supports_image_input"] is True

    # Explicit False is preserved (the exact failure mode the safety net
    # guards against — DeepSeek V3 over OpenRouter would 404 with "No
    # endpoints found that support image input").
    assert by_id[-2]["supports_image_input"] is False

    # Unannotated GPT-4o: resolver consults LiteLLM, which says vision.
    assert by_id[-10_010]["supports_image_input"] is True

    # Unknown / unmapped model: default-allow rather than pre-judge.
    assert by_id[-10_011]["supports_image_input"] is True

    for cfg in payload:
        assert "supports_image_input" in cfg, (
            f"supports_image_input missing from {cfg.get('id')}"
        )
        assert isinstance(cfg["supports_image_input"], bool)
