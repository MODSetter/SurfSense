"""Unit tests for ``_resolve_agent_billing_for_search_space``."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

pytestmark = pytest.mark.unit


class _FakeExecResult:
    def __init__(self, obj):
        self._obj = obj

    def scalars(self):
        return self

    def first(self):
        return self._obj


class _FakeSession:
    def __init__(self, responses: list):
        self._responses = list(responses)

    async def execute(self, _stmt):
        if not self._responses:
            return _FakeExecResult(None)
        return _FakeExecResult(self._responses.pop(0))


@dataclass
class _FakePinResolution:
    resolved_llm_config_id: int
    resolved_tier: str = "premium"
    from_existing_pin: bool = False


def _make_search_space(*, chat_model_id: int | None, user_id: UUID) -> SimpleNamespace:
    return SimpleNamespace(id=42, chat_model_id=chat_model_id, user_id=user_id)


def _make_byok_model(
    *, id_: int, base_model: str | None = None, model_id: str = "gpt-byok"
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id_,
        model_id=model_id,
        catalog={"base_model": base_model} if base_model else {},
        connection=SimpleNamespace(enabled=True, search_space_id=42, user_id=None),
    )


@pytest.mark.asyncio
async def test_auto_mode_with_thread_id_resolves_to_premium_global(monkeypatch):
    from app.services.billable_calls import _resolve_agent_billing_for_search_space

    user_id = uuid4()
    session = _FakeSession([_make_search_space(chat_model_id=0, user_id=user_id)])

    async def _fake_resolve_pin(*_args, **kwargs):
        assert kwargs["selected_llm_config_id"] == 0
        assert kwargs["thread_id"] == 99
        return _FakePinResolution(resolved_llm_config_id=-1, resolved_tier="premium")

    def _fake_get_global(cfg_id):
        if cfg_id == -1:
            return {
                "id": -1,
                "model_name": "gpt-5.4",
                "billing_tier": "premium",
                "litellm_params": {"base_model": "gpt-5.4"},
            }
        return None

    import app.services.auto_model_pin_service as pin_module
    import app.services.llm_service as llm_module

    monkeypatch.setattr(
        pin_module, "resolve_or_get_pinned_llm_config_id", _fake_resolve_pin
    )
    monkeypatch.setattr(llm_module, "get_global_llm_config", _fake_get_global)

    owner, tier, base_model = await _resolve_agent_billing_for_search_space(
        session, search_space_id=42, thread_id=99
    )

    assert owner == user_id
    assert tier == "premium"
    assert base_model == "gpt-5.4"


@pytest.mark.asyncio
async def test_auto_mode_with_thread_id_resolves_to_byok_is_free(monkeypatch):
    from app.services.billable_calls import _resolve_agent_billing_for_search_space

    user_id = uuid4()
    search_space = _make_search_space(chat_model_id=0, user_id=user_id)
    byok_model = _make_byok_model(
        id_=17, base_model="anthropic/claude-3-haiku", model_id="my-claude"
    )
    session = _FakeSession([search_space, byok_model])

    async def _fake_resolve_pin(*_args, **_kwargs):
        return _FakePinResolution(resolved_llm_config_id=17, resolved_tier="free")

    import app.services.auto_model_pin_service as pin_module

    monkeypatch.setattr(
        pin_module, "resolve_or_get_pinned_llm_config_id", _fake_resolve_pin
    )

    owner, tier, base_model = await _resolve_agent_billing_for_search_space(
        session, search_space_id=42, thread_id=99
    )

    assert owner == user_id
    assert tier == "free"
    assert base_model == "anthropic/claude-3-haiku"


@pytest.mark.asyncio
async def test_auto_mode_without_thread_id_falls_back_to_free():
    from app.services.billable_calls import _resolve_agent_billing_for_search_space

    user_id = uuid4()
    session = _FakeSession([_make_search_space(chat_model_id=0, user_id=user_id)])

    owner, tier, base_model = await _resolve_agent_billing_for_search_space(
        session, search_space_id=42, thread_id=None
    )

    assert owner == user_id
    assert tier == "free"
    assert base_model == "auto"


@pytest.mark.asyncio
async def test_auto_mode_pin_failure_falls_back_to_free(monkeypatch):
    from app.services.billable_calls import _resolve_agent_billing_for_search_space

    user_id = uuid4()
    session = _FakeSession([_make_search_space(chat_model_id=0, user_id=user_id)])

    async def _fake_resolve_pin(*args, **kwargs):
        raise ValueError("thread missing")

    import app.services.auto_model_pin_service as pin_module

    monkeypatch.setattr(
        pin_module, "resolve_or_get_pinned_llm_config_id", _fake_resolve_pin
    )

    owner, tier, base_model = await _resolve_agent_billing_for_search_space(
        session, search_space_id=42, thread_id=99
    )

    assert owner == user_id
    assert tier == "free"
    assert base_model == "auto"


@pytest.mark.asyncio
async def test_negative_id_premium_global_returns_premium(monkeypatch):
    from app.services.billable_calls import _resolve_agent_billing_for_search_space

    user_id = uuid4()
    session = _FakeSession([_make_search_space(chat_model_id=-1, user_id=user_id)])

    def _fake_get_global(cfg_id):
        return {
            "id": cfg_id,
            "model_name": "gpt-5.4",
            "billing_tier": "premium",
            "litellm_params": {"base_model": "gpt-5.4"},
        }

    import app.services.llm_service as llm_module

    monkeypatch.setattr(llm_module, "get_global_llm_config", _fake_get_global)

    owner, tier, base_model = await _resolve_agent_billing_for_search_space(
        session, search_space_id=42, thread_id=99
    )

    assert owner == user_id
    assert tier == "premium"
    assert base_model == "gpt-5.4"


@pytest.mark.asyncio
async def test_negative_id_missing_base_model_falls_back_to_model_name(monkeypatch):
    from app.services.billable_calls import _resolve_agent_billing_for_search_space

    user_id = uuid4()
    session = _FakeSession([_make_search_space(chat_model_id=-5, user_id=user_id)])

    def _fake_get_global(cfg_id):
        return {"id": cfg_id, "model_name": "fallback-model", "billing_tier": "premium"}

    import app.services.llm_service as llm_module

    monkeypatch.setattr(llm_module, "get_global_llm_config", _fake_get_global)

    _, tier, base_model = await _resolve_agent_billing_for_search_space(
        session, search_space_id=42
    )

    assert tier == "premium"
    assert base_model == "fallback-model"


@pytest.mark.asyncio
async def test_positive_id_byok_is_always_free():
    from app.services.billable_calls import _resolve_agent_billing_for_search_space

    user_id = uuid4()
    search_space = _make_search_space(chat_model_id=23, user_id=user_id)
    byok_model = _make_byok_model(id_=23, base_model="anthropic/claude-3.5-sonnet")
    session = _FakeSession([search_space, byok_model])

    owner, tier, base_model = await _resolve_agent_billing_for_search_space(
        session, search_space_id=42
    )

    assert owner == user_id
    assert tier == "free"
    assert base_model == "anthropic/claude-3.5-sonnet"


@pytest.mark.asyncio
async def test_positive_id_byok_missing_returns_free_with_empty_base_model():
    from app.services.billable_calls import _resolve_agent_billing_for_search_space

    user_id = uuid4()
    session = _FakeSession([_make_search_space(chat_model_id=99, user_id=user_id)])

    owner, tier, base_model = await _resolve_agent_billing_for_search_space(
        session, search_space_id=42
    )

    assert owner == user_id
    assert tier == "free"
    assert base_model == ""


@pytest.mark.asyncio
async def test_search_space_not_found_raises_value_error():
    from app.services.billable_calls import _resolve_agent_billing_for_search_space

    with pytest.raises(ValueError, match="Search space"):
        await _resolve_agent_billing_for_search_space(
            _FakeSession([None]), search_space_id=999
        )


@pytest.mark.asyncio
async def test_chat_model_id_none_raises_value_error():
    from app.services.billable_calls import _resolve_agent_billing_for_search_space

    user_id = uuid4()
    session = _FakeSession([_make_search_space(chat_model_id=None, user_id=user_id)])

    with pytest.raises(ValueError, match="chat_model_id"):
        await _resolve_agent_billing_for_search_space(session, search_space_id=42)
