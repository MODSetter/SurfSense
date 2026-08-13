"""Auto must never pin a model that cannot serve a chat completion.

This drives the real selection path — ``_generate_configs`` ->
``materialize_global_model_catalog`` -> ``_global_candidates`` ->
``_select_pin`` — across thousands of synthetic thread ids, and counts how
many threads land on a ``:batch`` variant.

Two scenarios, because the failure is episodic rather than constant.
``_select_pin`` is lock-first: it only considers Tier B (dynamic OpenRouter)
when no Tier A (operator-curated YAML) config is eligible. So Tier A healthy
hides the bug entirely, and Tier A in runtime cooldown exposes it. That is why
production saw multi-day quiet gaps between bursts of MODEL_NOT_FOUND.
"""

from __future__ import annotations

import pytest

from app.services.auto_model_pin_service import _global_candidates, _select_pin
from app.services.global_model_catalog import materialize_global_model_catalog
from app.services.openrouter_integration_service import _generate_configs

pytestmark = pytest.mark.unit

THREAD_COUNT = 2_000

# Frontier ids with their real shape: a `:batch` twin priced at half the
# base model. Both carry identical capability metadata upstream, which is
# what lets the batch variant tie with its twin and share the shortlist.
_FRONTIER = [
    ("anthropic/claude-sonnet-4.5", "0.000003", "0.000015"),
    ("google/gemini-3.6-flash", "0.0000003", "0.0000025"),
    ("openai/gpt-5.6-terra", "0.00000125", "0.00001"),
    ("x-ai/grok-4", "0.000003", "0.000015"),
]


def _or_model(model_id: str, prompt: str, completion: str) -> dict:
    return {
        "id": model_id,
        "name": model_id,
        "architecture": {"output_modalities": ["text"], "input_modalities": ["text"]},
        "supported_parameters": ["tools", "structured_outputs", "reasoning"],
        "context_length": 1_000_000,
        "pricing": {"prompt": prompt, "completion": completion},
    }


def _openrouter_payload() -> list[dict]:
    payload: list[dict] = []
    for model_id, prompt, completion in _FRONTIER:
        payload.append(_or_model(model_id, prompt, completion))
        payload.append(
            _or_model(
                f"{model_id}:batch",
                str(float(prompt) / 2),
                str(float(completion) / 2),
            )
        )
    return payload


def _yaml_configs() -> list[dict]:
    """Stand-ins for the operator-curated Azure entries that hold Tier A."""
    return [
        {
            "id": -1 - index,
            "name": model_name,
            "provider": "azure",
            "model_name": model_name,
            "api_key": "azure-key",
            "api_base": "https://example.openai.azure.com",
            "billing_tier": "premium",
            "auto_pin_tier": "A",
            "quality_score": 85,
            "quality_score_static": 85,
            "supports_tools": True,
            "supports_image_input": True,
        }
        for index, model_name in enumerate(
            ("azure/gpt-5.4", "azure/gpt-5.4-mini", "azure/gpt-5.3")
        )
    ]


@pytest.fixture
def catalogue(monkeypatch):
    """Install a realistic mixed catalogue into the config globals."""
    from app.config import config as app_config

    chat_configs = _yaml_configs() + _generate_configs(
        _openrouter_payload(),
        {
            "api_key": "sk-or-test",
            "id_offset": -10_000,
            "rpm": 200,
            "tpm": 1_000_000,
            "quota_reserve_tokens": 4000,
        },
    )
    connections, models = materialize_global_model_catalog(
        chat_configs=chat_configs, image_configs=[]
    )
    monkeypatch.setattr(app_config, "GLOBAL_LLM_CONFIGS", chat_configs)
    monkeypatch.setattr(app_config, "GLOBAL_CONNECTIONS", connections)
    monkeypatch.setattr(app_config, "GLOBAL_MODELS", models)
    return chat_configs


def _simulate(*, cooled_down_ids: set[int]) -> list[str]:
    """Return the model id pinned for each of ``THREAD_COUNT`` new threads."""
    candidates = _global_candidates(
        capability="chat", shared_cooled_down_ids=cooled_down_ids
    )
    assert candidates, "fixture produced no Auto candidates"
    return [
        _select_pin(candidates, thread_id)[0]["model_id"]
        for thread_id in range(1, THREAD_COUNT + 1)
    ]


def _batch_share(picks: list[str]) -> float:
    return sum(1 for pick in picks if pick.endswith(":batch")) / len(picks)


def test_no_batch_pin_when_tier_a_is_healthy(catalogue):
    picks = _simulate(cooled_down_ids=set())

    assert _batch_share(picks) == 0.0


def test_no_batch_pin_when_tier_a_is_cooled_down(catalogue):
    """The fallthrough case: every curated config is in runtime cooldown."""
    tier_a_ids = {
        int(cfg["id"]) for cfg in catalogue if cfg.get("auto_pin_tier") == "A"
    }

    picks = _simulate(cooled_down_ids=tier_a_ids)

    assert _batch_share(picks) == 0.0, (
        f"{_batch_share(picks):.0%} of threads pinned a `:batch` variant, "
        "which OpenRouter answers with 404"
    )
