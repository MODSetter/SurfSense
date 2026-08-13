"""A blocklisted model must be unreachable from every surface a user has.

The compatibility sweep is only worth running if its verdict actually removes
the model. There are three ways a user reaches one — the generated catalogue,
Auto's candidate pool, and the model picker payload — and all three read from
the same globals, so this asserts each one independently rather than trusting
that they stay wired together.
"""

from __future__ import annotations

import pytest

from app.routes.model_connections_routes import list_global_connections
from app.services.auto_model_pin_service import _global_candidates
from app.services.global_model_catalog import materialize_global_model_catalog
from app.services.openrouter_integration_service import _generate_configs

pytestmark = pytest.mark.unit

BLOCKED_ID = "some-provider/rejects-tool-results"
HEALTHY_ID = "anthropic/claude-sonnet-4.5"

_SETTINGS = {
    "api_key": "sk-or-test",
    "id_offset": -10_000,
    "rpm": 200,
    "tpm": 1_000_000,
    "quota_reserve_tokens": 4000,
}


def _or_model(model_id: str) -> dict:
    return {
        "id": model_id,
        "name": model_id,
        "architecture": {"output_modalities": ["text"], "input_modalities": ["text"]},
        "supported_parameters": ["tools"],
        "context_length": 1_000_000,
        "pricing": {"prompt": "0.000003", "completion": "0.000015"},
    }


@pytest.fixture
def catalogue(monkeypatch):
    """Build the live globals from a payload with one blocklisted model."""
    from app.config import config as app_config

    chat_configs = _generate_configs(
        [_or_model(HEALTHY_ID), _or_model(BLOCKED_ID)],
        _SETTINGS,
        {BLOCKED_ID},
    )
    connections, models = materialize_global_model_catalog(
        chat_configs=chat_configs, image_configs=[]
    )
    monkeypatch.setattr(app_config, "GLOBAL_LLM_CONFIGS", chat_configs)
    monkeypatch.setattr(app_config, "GLOBAL_CONNECTIONS", connections)
    monkeypatch.setattr(app_config, "GLOBAL_MODELS", models)
    return chat_configs


def test_blocked_model_is_absent_from_the_generated_catalogue(catalogue):
    model_names = {cfg["model_name"] for cfg in catalogue}

    assert HEALTHY_ID in model_names, "fixture removed the wrong model"
    assert BLOCKED_ID not in model_names


def test_blocked_model_is_absent_from_auto_candidates(catalogue):
    candidates = _global_candidates(capability="chat", shared_cooled_down_ids=set())

    assert {c["model_id"] for c in candidates} == {HEALTHY_ID}


@pytest.mark.asyncio
async def test_blocked_model_is_absent_from_the_picker_payload(catalogue):
    connections = await list_global_connections(auth=None)

    offered = {model.model_id for conn in connections for model in (conn.models or [])}
    assert HEALTHY_ID in offered
    assert BLOCKED_ID not in offered
