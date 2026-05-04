"""Unit tests for ``_resolve_agent_billing_for_search_space``.

Validates the resolver used by Celery podcast/video tasks to compute
``(owner_user_id, billing_tier, base_model)`` from a search space and its
agent LLM config. The resolver mirrors chat's billing-resolution pattern at
``stream_new_chat.py:2294-2351`` and is the single integration point that
prevents Auto-mode podcast/video from leaking premium credit.

Coverage:

* Auto mode + ``thread_id`` set, pin resolves to a negative-id premium
  global → returns ``("premium", <base_model>)``.
* Auto mode + ``thread_id`` set, pin resolves to a negative-id free
  global → returns ``("free", <base_model>)``.
* Auto mode + ``thread_id`` set, pin resolves to a positive-id BYOK config
  → always ``"free"``.
* Auto mode + ``thread_id=None`` → fallback to ``("free", "auto")`` without
  hitting the pin service.
* Negative id (no Auto) → uses ``get_global_llm_config``'s
  ``billing_tier``.
* Positive id (user BYOK) → always ``"free"``.
* Search space not found → raises ``ValueError``.
* ``agent_llm_id`` is None → raises ``ValueError``.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeExecResult:
    def __init__(self, obj):
        self._obj = obj

    def scalars(self):
        return self

    def first(self):
        return self._obj


class _FakeSession:
    """Tiny AsyncSession stub.

    ``responses`` is a list of objects to return from successive
    ``execute()`` calls (in order). The resolver makes at most two
    ``execute()`` calls (search-space lookup, then optionally NewLLMConfig
    lookup), so two queued responses cover the matrix.
    """

    def __init__(self, responses: list):
        self._responses = list(responses)

    async def execute(self, _stmt):
        if not self._responses:
            return _FakeExecResult(None)
        return _FakeExecResult(self._responses.pop(0))

    async def commit(self) -> None:
        pass


@dataclass
class _FakePinResolution:
    resolved_llm_config_id: int
    resolved_tier: str = "premium"
    from_existing_pin: bool = False


def _make_search_space(*, agent_llm_id: int | None, user_id: UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=42,
        agent_llm_id=agent_llm_id,
        user_id=user_id,
    )


def _make_byok_config(
    *, id_: int, base_model: str | None = None, model_name: str = "gpt-byok"
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id_,
        model_name=model_name,
        litellm_params={"base_model": base_model} if base_model else {},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_mode_with_thread_id_resolves_to_premium_global(monkeypatch):
    """Auto + thread → pin service resolves to negative-id premium config →
    resolver returns ``("premium", <base_model>)``."""
    from app.services.billable_calls import _resolve_agent_billing_for_search_space

    user_id = uuid4()
    session = _FakeSession([_make_search_space(agent_llm_id=0, user_id=user_id)])

    # Mock the pin service to return a concrete premium config id.
    async def _fake_resolve_pin(
        sess,
        *,
        thread_id,
        search_space_id,
        user_id,
        selected_llm_config_id,
        force_repin_free=False,
    ):
        assert selected_llm_config_id == 0
        assert thread_id == 99
        return _FakePinResolution(resolved_llm_config_id=-1, resolved_tier="premium")

    # Mock global config lookup to return a premium entry.
    def _fake_get_global(cfg_id):
        if cfg_id == -1:
            return {
                "id": -1,
                "model_name": "gpt-5.4",
                "billing_tier": "premium",
                "litellm_params": {"base_model": "gpt-5.4"},
            }
        return None

    # Lazy imports inside the resolver — patch the *target* modules so the
    # imported names resolve to our fakes.
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
async def test_auto_mode_with_thread_id_resolves_to_free_global(monkeypatch):
    """Auto + thread → pin returns negative-id free config → resolver
    returns ``("free", <base_model>)``. Same path the pin service takes for
    out-of-credit users (graceful degradation)."""
    from app.services.billable_calls import _resolve_agent_billing_for_search_space

    user_id = uuid4()
    session = _FakeSession([_make_search_space(agent_llm_id=0, user_id=user_id)])

    async def _fake_resolve_pin(
        sess,
        *,
        thread_id,
        search_space_id,
        user_id,
        selected_llm_config_id,
        force_repin_free=False,
    ):
        return _FakePinResolution(resolved_llm_config_id=-3, resolved_tier="free")

    def _fake_get_global(cfg_id):
        if cfg_id == -3:
            return {
                "id": -3,
                "model_name": "openrouter/free-model",
                "billing_tier": "free",
                "litellm_params": {"base_model": "openrouter/free-model"},
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
    assert tier == "free"
    assert base_model == "openrouter/free-model"


@pytest.mark.asyncio
async def test_auto_mode_with_thread_id_resolves_to_byok_is_free(monkeypatch):
    """Auto + thread → pin returns positive-id BYOK config → resolver
    returns ``("free", ...)`` (BYOK is always free per
    ``AgentConfig.from_new_llm_config``)."""
    from app.services.billable_calls import _resolve_agent_billing_for_search_space

    user_id = uuid4()
    search_space = _make_search_space(agent_llm_id=0, user_id=user_id)
    byok_cfg = _make_byok_config(
        id_=17, base_model="anthropic/claude-3-haiku", model_name="my-claude"
    )
    session = _FakeSession([search_space, byok_cfg])

    async def _fake_resolve_pin(
        sess,
        *,
        thread_id,
        search_space_id,
        user_id,
        selected_llm_config_id,
        force_repin_free=False,
    ):
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
    """Auto + ``thread_id=None`` → ``("free", "auto")`` without invoking
    the pin service. Forward-compat fallback for any future direct-API
    entrypoint that doesn't have a chat thread."""
    from app.services.billable_calls import _resolve_agent_billing_for_search_space

    user_id = uuid4()
    session = _FakeSession([_make_search_space(agent_llm_id=0, user_id=user_id)])

    owner, tier, base_model = await _resolve_agent_billing_for_search_space(
        session, search_space_id=42, thread_id=None
    )

    assert owner == user_id
    assert tier == "free"
    assert base_model == "auto"


@pytest.mark.asyncio
async def test_auto_mode_pin_failure_falls_back_to_free(monkeypatch):
    """If the pin service raises ``ValueError`` (thread missing /
    mismatched search space), the resolver should log and return free
    rather than killing the whole task."""
    from app.services.billable_calls import _resolve_agent_billing_for_search_space

    user_id = uuid4()
    session = _FakeSession([_make_search_space(agent_llm_id=0, user_id=user_id)])

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
    """Explicit negative agent_llm_id → ``get_global_llm_config`` →
    return its ``billing_tier``."""
    from app.services.billable_calls import _resolve_agent_billing_for_search_space

    user_id = uuid4()
    session = _FakeSession([_make_search_space(agent_llm_id=-1, user_id=user_id)])

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
async def test_negative_id_free_global_returns_free(monkeypatch):
    from app.services.billable_calls import _resolve_agent_billing_for_search_space

    user_id = uuid4()
    session = _FakeSession([_make_search_space(agent_llm_id=-2, user_id=user_id)])

    def _fake_get_global(cfg_id):
        return {
            "id": cfg_id,
            "model_name": "openrouter/some-free",
            "billing_tier": "free",
            "litellm_params": {"base_model": "openrouter/some-free"},
        }

    import app.services.llm_service as llm_module

    monkeypatch.setattr(llm_module, "get_global_llm_config", _fake_get_global)

    owner, tier, base_model = await _resolve_agent_billing_for_search_space(
        session, search_space_id=42, thread_id=None
    )

    assert owner == user_id
    assert tier == "free"
    assert base_model == "openrouter/some-free"


@pytest.mark.asyncio
async def test_negative_id_missing_base_model_falls_back_to_model_name(monkeypatch):
    """When the global config has no ``litellm_params.base_model``, the
    resolver falls back to ``model_name`` — matching chat's behavior."""
    from app.services.billable_calls import _resolve_agent_billing_for_search_space

    user_id = uuid4()
    session = _FakeSession([_make_search_space(agent_llm_id=-5, user_id=user_id)])

    def _fake_get_global(cfg_id):
        return {
            "id": cfg_id,
            "model_name": "fallback-model",
            "billing_tier": "premium",
            # No litellm_params.
        }

    import app.services.llm_service as llm_module

    monkeypatch.setattr(llm_module, "get_global_llm_config", _fake_get_global)

    _, tier, base_model = await _resolve_agent_billing_for_search_space(
        session, search_space_id=42
    )

    assert tier == "premium"
    assert base_model == "fallback-model"


@pytest.mark.asyncio
async def test_positive_id_byok_is_always_free():
    """Positive agent_llm_id → user-owned BYOK NewLLMConfig → always free,
    regardless of underlying provider tier."""
    from app.services.billable_calls import _resolve_agent_billing_for_search_space

    user_id = uuid4()
    search_space = _make_search_space(agent_llm_id=23, user_id=user_id)
    byok_cfg = _make_byok_config(id_=23, base_model="anthropic/claude-3.5-sonnet")
    session = _FakeSession([search_space, byok_cfg])

    owner, tier, base_model = await _resolve_agent_billing_for_search_space(
        session, search_space_id=42
    )

    assert owner == user_id
    assert tier == "free"
    assert base_model == "anthropic/claude-3.5-sonnet"


@pytest.mark.asyncio
async def test_positive_id_byok_missing_returns_free_with_empty_base_model():
    """If the BYOK config row is missing/deleted but the search space still
    points at it, the resolver still returns free (no debit) with an empty
    base_model — billable_call's premium path is skipped, no harm done."""
    from app.services.billable_calls import _resolve_agent_billing_for_search_space

    user_id = uuid4()
    session = _FakeSession([_make_search_space(agent_llm_id=99, user_id=user_id)])

    owner, tier, base_model = await _resolve_agent_billing_for_search_space(
        session, search_space_id=42
    )

    assert owner == user_id
    assert tier == "free"
    assert base_model == ""


@pytest.mark.asyncio
async def test_search_space_not_found_raises_value_error():
    from app.services.billable_calls import _resolve_agent_billing_for_search_space

    session = _FakeSession([None])

    with pytest.raises(ValueError, match="Search space"):
        await _resolve_agent_billing_for_search_space(session, search_space_id=999)


@pytest.mark.asyncio
async def test_agent_llm_id_none_raises_value_error():
    from app.services.billable_calls import _resolve_agent_billing_for_search_space

    user_id = uuid4()
    session = _FakeSession([_make_search_space(agent_llm_id=None, user_id=user_id)])

    with pytest.raises(ValueError, match="agent_llm_id"):
        await _resolve_agent_billing_for_search_space(session, search_space_id=42)
