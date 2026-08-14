"""A pin this worker cannot resolve must not end the turn.

Production runs ``UVICORN_WORKERS=4``. Uvicorn preforks, so each worker runs
``lifespan`` independently: four separate OpenRouter fetches at boot, four
24h refresh loops drifting by boot time, four in-memory catalogues. Pins live
in Postgres and are shared, so worker A can pin a config id that is missing
from worker B's ``GLOBAL_MODELS`` — either because B's boot fetch failed and
left it with YAML configs only, or because the two workers refreshed either
side of an upstream delisting.

These drive the orchestrator's real sequence (resolve the pin, then load the
bundle) against a catalogue that is missing the pinned id.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import app.tasks.chat.streaming.flows.shared.llm_bundle as llm_bundle
from app.services.auto_model_pin_service import (
    clear_healthy,
    clear_runtime_cooldown,
)
from app.tasks.chat.streaming.flows.new_chat.auto_pin import resolve_initial_auto_pin

pytestmark = pytest.mark.unit

WORKSPACE_ID = 10
# Pinned by another worker, absent from this worker's catalogue.
FOREIGN_PIN_ID = -4242


class _FakeRedis:
    def set(self, *_args, **_kwargs):
        return True

    def mget(self, keys: list[str]):
        return [None for _ in keys]

    def delete(self, *_keys):
        return 0

    def scan_iter(self, _pattern: str):
        return iter(())


class _FakeExecResult:
    def __init__(self, *, thread=None, scalars=None):
        self._thread = thread
        self._scalars = scalars or []

    def unique(self):
        return self

    def scalar_one_or_none(self):
        return self._thread

    def scalars(self):
        return SimpleNamespace(all=lambda: self._scalars, first=lambda: None)


class _FakeSession:
    """Returns the thread for the first query, no DB models for the rest."""

    def __init__(self, thread):
        self.thread = thread
        self.executes = 0

    async def execute(self, _stmt):
        self.executes += 1
        if self.executes == 1:
            return _FakeExecResult(thread=self.thread)
        return _FakeExecResult(scalars=[])

    async def commit(self):
        return None


@pytest.fixture(autouse=True)
def _catalogue(monkeypatch):
    """This worker's catalogue: two healthy models, neither is the pin."""
    import app.services.auto_model_pin_service as pin_service
    from app.config import config as app_config

    monkeypatch.setattr(pin_service, "_runtime_cooldown_redis", _FakeRedis())
    clear_runtime_cooldown()
    clear_healthy()

    configs = [
        {
            "id": -1,
            "name": "Curated Premium",
            "provider": "azure",
            "model_name": "azure/gpt-5.4",
            "api_key": "azure-key",
            "billing_tier": "premium",
            "auto_pin_tier": "A",
            "quality_score": 90,
        },
        {
            "id": -2,
            "name": "Curated Free",
            "provider": "azure",
            "model_name": "azure/gpt-5.4-mini",
            "api_key": "azure-key-2",
            "billing_tier": "free",
            "auto_pin_tier": "A",
            "quality_score": 70,
        },
    ]
    connections = [
        {
            "id": -100 - index,
            "provider": cfg["provider"],
            "api_key": cfg["api_key"],
            "base_url": None,
            "extra": {},
            "scope": "GLOBAL",
            "enabled": True,
        }
        for index, cfg in enumerate(configs)
    ]
    models = [
        {
            "id": cfg["id"],
            "connection_id": -100 - index,
            "model_id": cfg["model_name"],
            "display_name": cfg["name"],
            "supports_chat": True,
            "supports_tools": True,
            "supports_image_input": True,
            "supports_image_generation": False,
            "capabilities_override": {},
            "enabled": True,
            "billing_tier": cfg["billing_tier"],
            "catalog": {},
        }
        for index, cfg in enumerate(configs)
    ]

    monkeypatch.setattr(app_config, "GLOBAL_LLM_CONFIGS", configs)
    monkeypatch.setattr(app_config, "GLOBAL_CONNECTIONS", connections)
    monkeypatch.setattr(app_config, "GLOBAL_MODELS", models)

    async def _fake_workspace(_session: Any, _workspace_id: int):
        return SimpleNamespace(id=WORKSPACE_ID, user_id="user-1")

    monkeypatch.setattr(llm_bundle, "_load_workspace", _fake_workspace)
    monkeypatch.setattr(llm_bundle, "register_model_usage_metadata", lambda **_kw: None)
    monkeypatch.setattr(
        llm_bundle, "to_litellm", lambda _conn, model_id: (model_id, {"api_key": "k"})
    )

    yield

    clear_runtime_cooldown()
    clear_healthy()


async def _resolve_and_load(*, selected_llm_config_id: int):
    """Mirror the orchestrator: resolve the pin, then load the bundle."""
    session = _FakeSession(
        SimpleNamespace(
            id=1,
            workspace_id=WORKSPACE_ID,
            pinned_llm_config_id=FOREIGN_PIN_ID,
        )
    )
    pin_result = await resolve_initial_auto_pin(
        session,
        chat_id=1,
        workspace_id=WORKSPACE_ID,
        user_id="00000000-0000-0000-0000-000000000001",
        selected_llm_config_id=selected_llm_config_id,
        requires_image_input=False,
        requested_llm_config_id=selected_llm_config_id,
    )
    if pin_result.error is not None:
        return pin_result.error[0], None
    _, _, load_error = await llm_bundle.load_llm_bundle(
        session,
        config_id=pin_result.llm_config_id,
        workspace_id=WORKSPACE_ID,
    )
    return load_error, pin_result.llm_config_id


async def test_auto_repins_when_the_pin_is_missing_here(monkeypatch):
    """Auto already self-heals: an unresolvable pin drops out of the pool."""
    monkeypatch.setattr(
        "app.services.auto_model_pin_service.TokenQuotaService.credit_get_usage",
        lambda *_a, **_kw: _allowed(),
    )

    error, resolved_id = await _resolve_and_load(selected_llm_config_id=0)

    assert error is None
    assert resolved_id in {-1, -2}


async def test_explicit_selection_of_a_missing_model_recovers():
    """The gap Auto does not cover.

    A workspace-level ``chat_model_id`` bypasses the Auto pool entirely, so a
    config id this worker never materialized used to go straight to the bundle
    loader and end the turn with SERVER_ERROR — while the identical request
    succeeded on a sibling worker, which is what made it look intermittent.
    """
    error, resolved_id = await _resolve_and_load(selected_llm_config_id=FOREIGN_PIN_ID)

    assert error is None, f"turn ended with {error!r} instead of recovering"
    assert resolved_id in {-1, -2}


async def _allowed():
    return SimpleNamespace(allowed=True)
