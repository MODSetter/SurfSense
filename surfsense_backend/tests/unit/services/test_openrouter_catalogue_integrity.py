"""Guard the two ways a user can reach a model that cannot answer.

Both were confirmed live against OpenRouter (see
``scripts/probe_openrouter_dead_models.py``):

- ``*:batch`` ids are listed in ``/models`` with full chat metadata but reject
  chat completions with ``404 "This model is only available through the Batch
  API"``. 59 of the 61 batch variants in the live catalogue passed our filter.
- ``refresh()`` rewrites ``GLOBAL_LLM_CONFIGS`` but never re-materializes
  ``GLOBAL_MODELS``, which is what the picker and ``load_llm_bundle`` actually
  read, so a model delisted upstream stays selectable until the next restart.

These assert on the generated catalogue rather than on the filter helpers,
because an earlier fix edited a filter that nothing calls and looked correct.
"""

from __future__ import annotations

import pytest

from app.services.openrouter_integration_service import (
    OpenRouterIntegrationService,
    _generate_configs,
)

pytestmark = pytest.mark.unit


def _model(model_id: str, *, name: str | None = None) -> dict:
    """A synthetic ``/api/v1/models`` entry that passes every other filter."""
    return {
        "id": model_id,
        "name": name or model_id,
        "architecture": {"output_modalities": ["text"], "input_modalities": ["text"]},
        "supported_parameters": ["tools"],
        "context_length": 200_000,
        "pricing": {"prompt": "0.000003", "completion": "0.000015"},
    }


_SETTINGS: dict = {
    "api_key": "sk-or-test",
    "id_offset": -10_000,
    "rpm": 200,
    "tpm": 1_000_000,
    "free_rpm": 20,
    "free_tpm": 100_000,
    "quota_reserve_tokens": 4000,
}


def test_generate_configs_excludes_batch_variants():
    """A ``:batch`` id must never become a config; its full-price twin must."""
    raw = [
        _model("anthropic/claude-sonnet-4.5"),
        _model("anthropic/claude-sonnet-4.5:batch"),
        _model("google/gemini-3.6-flash:batch"),
    ]

    model_names = {c["model_name"] for c in _generate_configs(raw, dict(_SETTINGS))}

    assert model_names == {"anthropic/claude-sonnet-4.5"}


def test_generate_configs_keeps_free_variant():
    """``:free`` is a real routable variant — the batch filter must not eat it."""
    raw = [
        _model("meta-llama/llama-3.3-70b-instruct:free"),
        _model("meta-llama/llama-3.3-70b-instruct:batch"),
    ]

    model_names = {c["model_name"] for c in _generate_configs(raw, dict(_SETTINGS))}

    assert model_names == {"meta-llama/llama-3.3-70b-instruct:free"}


@pytest.mark.asyncio
async def test_refresh_rematerializes_global_models(monkeypatch):
    """After ``refresh()``, GLOBAL_MODELS must track GLOBAL_LLM_CONFIGS.

    A model delisted upstream has to disappear from the catalogue the picker
    reads, and a newly listed one has to appear, without waiting for a restart.
    """
    from app.config import config as app_config, refresh_global_model_catalog

    service = OpenRouterIntegrationService()
    service._settings = dict(_SETTINGS)

    async def _no_health(*_args, **_kwargs) -> None:
        return None

    monkeypatch.setattr(service, "_enrich_health_safely", _no_health)
    monkeypatch.setattr(
        "app.services.pricing_registration.register_pricing_from_global_configs",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(
        "app.services.llm_router_service.LLMRouterService.rebuild",
        lambda *a, **kw: None,
    )

    # Boot state: two models live, catalogue materialized as it is at startup.
    boot = [_model("openai/gpt-4o"), _model("poolside/laguna-m.1")]
    monkeypatch.setattr(app_config, "GLOBAL_LLM_CONFIGS", [])
    monkeypatch.setattr(app_config, "GLOBAL_IMAGE_GEN_CONFIGS", [])
    monkeypatch.setattr(app_config, "GLOBAL_CONNECTIONS", [])
    monkeypatch.setattr(app_config, "GLOBAL_MODELS", [])
    app_config.GLOBAL_LLM_CONFIGS = _generate_configs(boot, dict(_SETTINGS))
    refresh_global_model_catalog()

    assert {m["model_id"] for m in app_config.GLOBAL_MODELS} == {
        "openai/gpt-4o",
        "poolside/laguna-m.1",
    }

    # Upstream drops laguna and lists a new model.
    async def _fetch(*_args, **_kwargs):
        return [_model("openai/gpt-4o"), _model("x-ai/grok-4")]

    monkeypatch.setattr(
        "app.services.openrouter_integration_service._fetch_models_async", _fetch
    )

    await service.refresh()

    assert {m["model_id"] for m in app_config.GLOBAL_MODELS} == {
        "openai/gpt-4o",
        "x-ai/grok-4",
    }
