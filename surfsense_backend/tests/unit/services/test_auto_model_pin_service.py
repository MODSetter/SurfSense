from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from app.services.auto_model_pin_service import (
    AUTO_FASTEST_MODE,
    resolve_or_get_pinned_llm_config_id,
)

pytestmark = pytest.mark.unit


@dataclass
class _FakeQuotaResult:
    allowed: bool


class _FakeExecResult:
    def __init__(self, thread):
        self._thread = thread

    def unique(self):
        return self

    def scalar_one_or_none(self):
        return self._thread


class _FakeSession:
    def __init__(self, thread):
        self.thread = thread
        self.commit_count = 0

    async def execute(self, _stmt):
        return _FakeExecResult(self.thread)

    async def commit(self):
        self.commit_count += 1


def _thread(
    *,
    search_space_id: int = 10,
    pinned_llm_config_id: int | None = None,
    pinned_auto_mode: str | None = None,
):
    return SimpleNamespace(
        id=1,
        search_space_id=search_space_id,
        pinned_llm_config_id=pinned_llm_config_id,
        pinned_auto_mode=pinned_auto_mode,
        pinned_at=None,
    )


@pytest.mark.asyncio
async def test_auto_first_turn_pins_one_model(monkeypatch):
    from app.config import config

    session = _FakeSession(_thread())
    monkeypatch.setattr(
        config,
        "GLOBAL_LLM_CONFIGS",
        [
            {"id": -2, "provider": "OPENAI", "model_name": "gpt-free", "api_key": "k1"},
            {"id": -1, "provider": "OPENAI", "model_name": "gpt-prem", "api_key": "k2", "billing_tier": "premium"},
        ],
    )

    async def _allowed(*_args, **_kwargs):
        return _FakeQuotaResult(allowed=True)

    monkeypatch.setattr(
        "app.services.auto_model_pin_service.TokenQuotaService.premium_get_usage",
        _allowed,
    )

    result = await resolve_or_get_pinned_llm_config_id(
        session,
        thread_id=1,
        search_space_id=10,
        user_id="00000000-0000-0000-0000-000000000001",
        selected_llm_config_id=0,
    )
    assert result.resolved_llm_config_id in {-1, -2}
    assert session.thread.pinned_llm_config_id == result.resolved_llm_config_id
    assert session.thread.pinned_auto_mode == AUTO_FASTEST_MODE
    assert session.thread.pinned_at is not None
    assert session.commit_count == 1


@pytest.mark.asyncio
async def test_next_turn_reuses_existing_pin(monkeypatch):
    from app.config import config

    session = _FakeSession(
        _thread(pinned_llm_config_id=-1, pinned_auto_mode=AUTO_FASTEST_MODE)
    )
    monkeypatch.setattr(
        config,
        "GLOBAL_LLM_CONFIGS",
        [
            {"id": -1, "provider": "OPENAI", "model_name": "gpt-prem", "api_key": "k2", "billing_tier": "premium"},
        ],
    )

    async def _must_not_call(*_args, **_kwargs):
        raise AssertionError("premium_get_usage should not be called for valid pin reuse")

    monkeypatch.setattr(
        "app.services.auto_model_pin_service.TokenQuotaService.premium_get_usage",
        _must_not_call,
    )

    result = await resolve_or_get_pinned_llm_config_id(
        session,
        thread_id=1,
        search_space_id=10,
        user_id="00000000-0000-0000-0000-000000000001",
        selected_llm_config_id=0,
    )
    assert result.resolved_llm_config_id == -1
    assert result.from_existing_pin is True
    assert session.commit_count == 0


@pytest.mark.asyncio
async def test_premium_eligible_auto_can_pin_premium(monkeypatch):
    from app.config import config

    session = _FakeSession(_thread())
    monkeypatch.setattr(
        config,
        "GLOBAL_LLM_CONFIGS",
        [
            {"id": -1, "provider": "OPENAI", "model_name": "gpt-prem", "api_key": "k2", "billing_tier": "premium"},
        ],
    )

    async def _allowed(*_args, **_kwargs):
        return _FakeQuotaResult(allowed=True)

    monkeypatch.setattr(
        "app.services.auto_model_pin_service.TokenQuotaService.premium_get_usage",
        _allowed,
    )

    result = await resolve_or_get_pinned_llm_config_id(
        session,
        thread_id=1,
        search_space_id=10,
        user_id="00000000-0000-0000-0000-000000000001",
        selected_llm_config_id=0,
    )
    assert result.resolved_llm_config_id == -1
    assert result.resolved_tier == "premium"


@pytest.mark.asyncio
async def test_premium_ineligible_auto_pins_free_only(monkeypatch):
    from app.config import config

    session = _FakeSession(_thread())
    monkeypatch.setattr(
        config,
        "GLOBAL_LLM_CONFIGS",
        [
            {"id": -2, "provider": "OPENAI", "model_name": "gpt-free", "api_key": "k1", "billing_tier": "free"},
            {"id": -1, "provider": "OPENAI", "model_name": "gpt-prem", "api_key": "k2", "billing_tier": "premium"},
        ],
    )

    async def _blocked(*_args, **_kwargs):
        return _FakeQuotaResult(allowed=False)

    monkeypatch.setattr(
        "app.services.auto_model_pin_service.TokenQuotaService.premium_get_usage",
        _blocked,
    )

    result = await resolve_or_get_pinned_llm_config_id(
        session,
        thread_id=1,
        search_space_id=10,
        user_id="00000000-0000-0000-0000-000000000001",
        selected_llm_config_id=0,
    )
    assert result.resolved_llm_config_id == -2
    assert result.resolved_tier == "free"


@pytest.mark.asyncio
async def test_pinned_premium_stays_premium_after_quota_exhaustion(monkeypatch):
    from app.config import config

    session = _FakeSession(
        _thread(pinned_llm_config_id=-1, pinned_auto_mode=AUTO_FASTEST_MODE)
    )
    monkeypatch.setattr(
        config,
        "GLOBAL_LLM_CONFIGS",
        [
            {"id": -2, "provider": "OPENAI", "model_name": "gpt-free", "api_key": "k1", "billing_tier": "free"},
            {"id": -1, "provider": "OPENAI", "model_name": "gpt-prem", "api_key": "k2", "billing_tier": "premium"},
        ],
    )

    async def _blocked(*_args, **_kwargs):
        return _FakeQuotaResult(allowed=False)

    monkeypatch.setattr(
        "app.services.auto_model_pin_service.TokenQuotaService.premium_get_usage",
        _blocked,
    )

    result = await resolve_or_get_pinned_llm_config_id(
        session,
        thread_id=1,
        search_space_id=10,
        user_id="00000000-0000-0000-0000-000000000001",
        selected_llm_config_id=0,
    )
    assert result.resolved_llm_config_id == -1
    assert result.from_existing_pin is True


@pytest.mark.asyncio
async def test_force_repin_free_switches_auto_premium_pin_to_free(monkeypatch):
    from app.config import config

    session = _FakeSession(
        _thread(pinned_llm_config_id=-1, pinned_auto_mode=AUTO_FASTEST_MODE)
    )
    monkeypatch.setattr(
        config,
        "GLOBAL_LLM_CONFIGS",
        [
            {"id": -2, "provider": "OPENAI", "model_name": "gpt-free", "api_key": "k1", "billing_tier": "free"},
            {"id": -1, "provider": "OPENAI", "model_name": "gpt-prem", "api_key": "k2", "billing_tier": "premium"},
        ],
    )

    async def _blocked(*_args, **_kwargs):
        return _FakeQuotaResult(allowed=False)

    monkeypatch.setattr(
        "app.services.auto_model_pin_service.TokenQuotaService.premium_get_usage",
        _blocked,
    )

    result = await resolve_or_get_pinned_llm_config_id(
        session,
        thread_id=1,
        search_space_id=10,
        user_id="00000000-0000-0000-0000-000000000001",
        selected_llm_config_id=0,
        force_repin_free=True,
    )
    assert result.resolved_llm_config_id == -2
    assert result.resolved_tier == "free"
    assert result.from_existing_pin is False
    assert session.thread.pinned_llm_config_id == -2


@pytest.mark.asyncio
async def test_explicit_user_model_change_clears_pin(monkeypatch):
    from app.config import config

    session = _FakeSession(
        _thread(pinned_llm_config_id=-2, pinned_auto_mode=AUTO_FASTEST_MODE)
    )
    monkeypatch.setattr(
        config,
        "GLOBAL_LLM_CONFIGS",
        [
            {"id": -2, "provider": "OPENAI", "model_name": "gpt-free", "api_key": "k1"},
        ],
    )

    result = await resolve_or_get_pinned_llm_config_id(
        session,
        thread_id=1,
        search_space_id=10,
        user_id="00000000-0000-0000-0000-000000000001",
        selected_llm_config_id=7,
    )
    assert result.resolved_llm_config_id == 7
    assert session.thread.pinned_llm_config_id is None
    assert session.thread.pinned_auto_mode is None
    assert session.thread.pinned_at is None
    assert session.commit_count == 1


@pytest.mark.asyncio
async def test_invalid_pinned_config_repairs_with_new_pin(monkeypatch):
    from app.config import config

    session = _FakeSession(
        _thread(pinned_llm_config_id=-999, pinned_auto_mode=AUTO_FASTEST_MODE)
    )
    monkeypatch.setattr(
        config,
        "GLOBAL_LLM_CONFIGS",
        [
            {"id": -2, "provider": "OPENAI", "model_name": "gpt-free", "api_key": "k1"},
        ],
    )

    async def _allowed(*_args, **_kwargs):
        return _FakeQuotaResult(allowed=True)

    monkeypatch.setattr(
        "app.services.auto_model_pin_service.TokenQuotaService.premium_get_usage",
        _allowed,
    )

    result = await resolve_or_get_pinned_llm_config_id(
        session,
        thread_id=1,
        search_space_id=10,
        user_id="00000000-0000-0000-0000-000000000001",
        selected_llm_config_id=0,
    )
    assert result.resolved_llm_config_id == -2
    assert session.thread.pinned_llm_config_id == -2
    assert session.commit_count == 1
