from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from app.services.auto_model_pin_service import (
    clear_healthy,
    clear_runtime_cooldown,
    is_recently_healthy,
    mark_healthy,
    mark_runtime_cooldown,
    resolve_or_get_pinned_llm_config_id,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clear_runtime_cooldown_map():
    clear_runtime_cooldown()
    clear_healthy()
    yield
    clear_runtime_cooldown()
    clear_healthy()


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
):
    return SimpleNamespace(
        id=1,
        search_space_id=search_space_id,
        pinned_llm_config_id=pinned_llm_config_id,
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
            {
                "id": -1,
                "provider": "OPENAI",
                "model_name": "gpt-prem",
                "api_key": "k2",
                "billing_tier": "premium",
            },
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
    assert session.thread.pinned_llm_config_id == result.resolved_llm_config_id
    assert session.commit_count == 1


@pytest.mark.asyncio
async def test_premium_eligible_auto_prefers_premium_over_free(monkeypatch):
    from app.config import config

    session = _FakeSession(_thread())
    monkeypatch.setattr(
        config,
        "GLOBAL_LLM_CONFIGS",
        [
            {
                "id": -2,
                "provider": "OPENAI",
                "model_name": "gpt-free",
                "api_key": "k1",
                "billing_tier": "free",
                "quality_score": 100,
            },
            {
                "id": -1,
                "provider": "OPENAI",
                "model_name": "gpt-prem",
                "api_key": "k2",
                "billing_tier": "premium",
                "quality_score": 10,
            },
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
async def test_next_turn_reuses_existing_pin(monkeypatch):
    from app.config import config

    session = _FakeSession(_thread(pinned_llm_config_id=-1))
    monkeypatch.setattr(
        config,
        "GLOBAL_LLM_CONFIGS",
        [
            {
                "id": -1,
                "provider": "OPENAI",
                "model_name": "gpt-prem",
                "api_key": "k2",
                "billing_tier": "premium",
            },
        ],
    )

    async def _must_not_call(*_args, **_kwargs):
        raise AssertionError(
            "premium_get_usage should not be called for valid pin reuse"
        )

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
            {
                "id": -1,
                "provider": "OPENAI",
                "model_name": "gpt-prem",
                "api_key": "k2",
                "billing_tier": "premium",
            },
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
            {
                "id": -2,
                "provider": "OPENAI",
                "model_name": "gpt-free",
                "api_key": "k1",
                "billing_tier": "free",
            },
            {
                "id": -1,
                "provider": "OPENAI",
                "model_name": "gpt-prem",
                "api_key": "k2",
                "billing_tier": "premium",
            },
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

    session = _FakeSession(_thread(pinned_llm_config_id=-1))
    monkeypatch.setattr(
        config,
        "GLOBAL_LLM_CONFIGS",
        [
            {
                "id": -2,
                "provider": "OPENAI",
                "model_name": "gpt-free",
                "api_key": "k1",
                "billing_tier": "free",
            },
            {
                "id": -1,
                "provider": "OPENAI",
                "model_name": "gpt-prem",
                "api_key": "k2",
                "billing_tier": "premium",
            },
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

    session = _FakeSession(_thread(pinned_llm_config_id=-1))
    monkeypatch.setattr(
        config,
        "GLOBAL_LLM_CONFIGS",
        [
            {
                "id": -2,
                "provider": "OPENAI",
                "model_name": "gpt-free",
                "api_key": "k1",
                "billing_tier": "free",
            },
            {
                "id": -1,
                "provider": "OPENAI",
                "model_name": "gpt-prem",
                "api_key": "k2",
                "billing_tier": "premium",
            },
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

    session = _FakeSession(_thread(pinned_llm_config_id=-2))
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
    assert session.commit_count == 1


@pytest.mark.asyncio
async def test_invalid_pinned_config_repairs_with_new_pin(monkeypatch):
    from app.config import config

    session = _FakeSession(_thread(pinned_llm_config_id=-999))
    monkeypatch.setattr(
        config,
        "GLOBAL_LLM_CONFIGS",
        [
            {"id": -2, "provider": "OPENAI", "model_name": "gpt-free", "api_key": "k1"},
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
    assert session.thread.pinned_llm_config_id == -2
    assert session.commit_count == 1


# ---------------------------------------------------------------------------
# Quality-aware pin selection (Auto Fastest upgrade)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_gated_config_is_excluded_from_selection(monkeypatch):
    """A cfg flagged ``health_gated`` must never be picked even if it has
    the highest score among eligible cfgs."""
    from app.config import config

    session = _FakeSession(_thread())
    monkeypatch.setattr(
        config,
        "GLOBAL_LLM_CONFIGS",
        [
            {
                "id": -1,
                "provider": "OPENROUTER",
                "model_name": "venice/dead-model",
                "api_key": "k1",
                "billing_tier": "free",
                "auto_pin_tier": "C",
                "quality_score": 95,
                "health_gated": True,
            },
            {
                "id": -2,
                "provider": "OPENROUTER",
                "model_name": "google/gemini-flash",
                "api_key": "k1",
                "billing_tier": "free",
                "auto_pin_tier": "C",
                "quality_score": 60,
                "health_gated": False,
            },
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


@pytest.mark.asyncio
async def test_tier_a_locks_first_premium_user_skips_or(monkeypatch):
    """Premium-eligible users with Tier A available should never spill to
    Tier B even if a B cfg ranks higher by ``quality_score``."""
    from app.config import config

    session = _FakeSession(_thread())
    monkeypatch.setattr(
        config,
        "GLOBAL_LLM_CONFIGS",
        [
            {
                "id": -1,
                "provider": "AZURE_OPENAI",
                "model_name": "gpt-5",
                "api_key": "k-yaml",
                "billing_tier": "premium",
                "auto_pin_tier": "A",
                "quality_score": 70,
                "health_gated": False,
            },
            {
                "id": -2,
                "provider": "OPENROUTER",
                "model_name": "openai/gpt-5",
                "api_key": "k-or",
                "billing_tier": "premium",
                "auto_pin_tier": "B",
                "quality_score": 95,
                "health_gated": False,
            },
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
async def test_tier_a_falls_through_to_or_when_a_pool_empty_for_user(monkeypatch):
    """Free-only user with no Tier A free cfg should pick from Tier C."""
    from app.config import config

    session = _FakeSession(_thread())
    monkeypatch.setattr(
        config,
        "GLOBAL_LLM_CONFIGS",
        [
            {
                "id": -1,
                "provider": "AZURE_OPENAI",
                "model_name": "gpt-5",
                "api_key": "k-yaml",
                "billing_tier": "premium",
                "auto_pin_tier": "A",
                "quality_score": 100,
                "health_gated": False,
            },
            {
                "id": -2,
                "provider": "OPENROUTER",
                "model_name": "google/gemini-flash:free",
                "api_key": "k-or",
                "billing_tier": "free",
                "auto_pin_tier": "C",
                "quality_score": 60,
                "health_gated": False,
            },
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


@pytest.mark.asyncio
async def test_top_k_picks_only_high_score_models(monkeypatch):
    """Different thread IDs should spread across top-K, never pick the
    obvious low-quality cfg even when it sits in the candidate list."""
    from app.config import config

    high_score_cfgs = [
        {
            "id": -i,
            "provider": "AZURE_OPENAI",
            "model_name": f"gpt-x-{i}",
            "api_key": "k",
            "billing_tier": "premium",
            "auto_pin_tier": "A",
            "quality_score": 90,
            "health_gated": False,
        }
        for i in range(1, 6)  # 5 high-quality Tier A cfgs
    ]
    low_score_trap = {
        "id": -99,
        "provider": "AZURE_OPENAI",
        "model_name": "tiny-legacy",
        "api_key": "k",
        "billing_tier": "premium",
        "auto_pin_tier": "A",
        "quality_score": 10,
        "health_gated": False,
    }
    monkeypatch.setattr(
        config,
        "GLOBAL_LLM_CONFIGS",
        [*high_score_cfgs, low_score_trap],
    )

    async def _allowed(*_args, **_kwargs):
        return _FakeQuotaResult(allowed=True)

    monkeypatch.setattr(
        "app.services.auto_model_pin_service.TokenQuotaService.premium_get_usage",
        _allowed,
    )

    high_score_ids = {c["id"] for c in high_score_cfgs}
    seen = set()
    for thread_id in range(1, 50):
        session = _FakeSession(_thread())
        result = await resolve_or_get_pinned_llm_config_id(
            session,
            thread_id=thread_id,
            search_space_id=10,
            user_id="00000000-0000-0000-0000-000000000001",
            selected_llm_config_id=0,
        )
        seen.add(result.resolved_llm_config_id)
        assert result.resolved_llm_config_id != -99, (
            "low-score trap cfg should never be picked"
        )
        assert result.resolved_llm_config_id in high_score_ids

    # Spread across at least a couple of top-K cfgs.
    assert len(seen) > 1


@pytest.mark.asyncio
async def test_pin_reuse_survives_health_gating_for_existing_pin(monkeypatch):
    """An *already* pinned cfg that later flips to ``health_gated`` should
    still not be reused — gated cfgs are filtered out of the candidate
    pool, which forces a repair to a healthy cfg.

    This guards the no-silent-tier-switch invariant: we don't keep using
    a known-broken model just because the thread happened to be pinned
    to it before the gate fired."""
    from app.config import config

    session = _FakeSession(_thread(pinned_llm_config_id=-1))
    monkeypatch.setattr(
        config,
        "GLOBAL_LLM_CONFIGS",
        [
            {
                "id": -1,
                "provider": "OPENROUTER",
                "model_name": "venice/dead-model",
                "api_key": "k",
                "billing_tier": "premium",
                "auto_pin_tier": "B",
                "quality_score": 50,
                "health_gated": True,
            },
            {
                "id": -2,
                "provider": "AZURE_OPENAI",
                "model_name": "gpt-5",
                "api_key": "k",
                "billing_tier": "premium",
                "auto_pin_tier": "A",
                "quality_score": 90,
                "health_gated": False,
            },
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
    assert result.from_existing_pin is False


@pytest.mark.asyncio
async def test_pin_reuse_regression_existing_healthy_pin(monkeypatch):
    """Existing pin reuse must short-circuit the new tier/score logic."""
    from app.config import config

    session = _FakeSession(_thread(pinned_llm_config_id=-1))
    monkeypatch.setattr(
        config,
        "GLOBAL_LLM_CONFIGS",
        [
            {
                "id": -1,
                "provider": "AZURE_OPENAI",
                "model_name": "gpt-5",
                "api_key": "k",
                "billing_tier": "premium",
                "auto_pin_tier": "A",
                "quality_score": 50,  # lower than -2
                "health_gated": False,
            },
            {
                "id": -2,
                "provider": "AZURE_OPENAI",
                "model_name": "gpt-5-pro",
                "api_key": "k",
                "billing_tier": "premium",
                "auto_pin_tier": "A",
                "quality_score": 99,
                "health_gated": False,
            },
        ],
    )

    async def _must_not_call(*_args, **_kwargs):
        raise AssertionError("premium_get_usage should not run on pin reuse")

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
async def test_runtime_cooled_down_pin_is_not_reused(monkeypatch):
    """A runtime-cooled config should be excluded from candidate reuse.

    This enables one-shot recovery from transient provider 429 bursts: we can
    mark the pinned cfg as cooled down and force a repair to another eligible
    cfg on the next resolution.
    """
    from app.config import config

    session = _FakeSession(_thread(pinned_llm_config_id=-1))
    monkeypatch.setattr(
        config,
        "GLOBAL_LLM_CONFIGS",
        [
            {
                "id": -1,
                "provider": "OPENROUTER",
                "model_name": "google/gemma-4-26b-a4b-it:free",
                "api_key": "k",
                "billing_tier": "free",
                "auto_pin_tier": "C",
                "quality_score": 90,
                "health_gated": False,
            },
            {
                "id": -2,
                "provider": "OPENROUTER",
                "model_name": "google/gemini-2.5-flash:free",
                "api_key": "k",
                "billing_tier": "free",
                "auto_pin_tier": "C",
                "quality_score": 80,
                "health_gated": False,
            },
        ],
    )

    async def _blocked(*_args, **_kwargs):
        return _FakeQuotaResult(allowed=False)

    monkeypatch.setattr(
        "app.services.auto_model_pin_service.TokenQuotaService.premium_get_usage",
        _blocked,
    )

    mark_runtime_cooldown(-1, reason="provider_rate_limited", cooldown_seconds=600)

    result = await resolve_or_get_pinned_llm_config_id(
        session,
        thread_id=1,
        search_space_id=10,
        user_id="00000000-0000-0000-0000-000000000001",
        selected_llm_config_id=0,
    )
    assert result.resolved_llm_config_id == -2
    assert result.from_existing_pin is False


@pytest.mark.asyncio
async def test_clearing_runtime_cooldown_restores_pin_reuse(monkeypatch):
    from app.config import config

    session = _FakeSession(_thread(pinned_llm_config_id=-1))
    monkeypatch.setattr(
        config,
        "GLOBAL_LLM_CONFIGS",
        [
            {
                "id": -1,
                "provider": "OPENROUTER",
                "model_name": "google/gemma-4-26b-a4b-it:free",
                "api_key": "k",
                "billing_tier": "free",
                "auto_pin_tier": "C",
                "quality_score": 90,
                "health_gated": False,
            },
        ],
    )

    async def _must_not_call(*_args, **_kwargs):
        raise AssertionError("premium_get_usage should not run on healthy pin reuse")

    monkeypatch.setattr(
        "app.services.auto_model_pin_service.TokenQuotaService.premium_get_usage",
        _must_not_call,
    )

    mark_runtime_cooldown(-1, reason="provider_rate_limited", cooldown_seconds=600)
    clear_runtime_cooldown(-1)

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
async def test_auto_pin_repin_excludes_previous_config_on_runtime_retry(monkeypatch):
    """Runtime retry should never repin the just-failed config."""
    from app.config import config

    session = _FakeSession(_thread(pinned_llm_config_id=-1))
    monkeypatch.setattr(
        config,
        "GLOBAL_LLM_CONFIGS",
        [
            {
                "id": -1,
                "provider": "OPENROUTER",
                "model_name": "google/gemma-4-26b-a4b-it:free",
                "api_key": "k",
                "billing_tier": "free",
                "auto_pin_tier": "C",
                "quality_score": 90,
                "health_gated": False,
            },
            {
                "id": -2,
                "provider": "OPENROUTER",
                "model_name": "google/gemini-2.5-flash:free",
                "api_key": "k",
                "billing_tier": "free",
                "auto_pin_tier": "C",
                "quality_score": 80,
                "health_gated": False,
            },
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
        exclude_config_ids={-1},
    )
    assert result.resolved_llm_config_id == -2
    assert result.from_existing_pin is False


# ---------------------------------------------------------------------------
# Healthy-status cache (preflight TTL companion)
# ---------------------------------------------------------------------------


def test_mark_healthy_then_is_recently_healthy_true_within_ttl():
    mark_healthy(-42, ttl_seconds=60)
    assert is_recently_healthy(-42) is True


def test_healthy_expires_after_ttl(monkeypatch):
    import app.services.auto_model_pin_service as svc

    real_time = svc.time.time
    base = real_time()

    monkeypatch.setattr(svc.time, "time", lambda: base)
    mark_healthy(-7, ttl_seconds=10)
    assert is_recently_healthy(-7) is True

    monkeypatch.setattr(svc.time, "time", lambda: base + 11)
    assert is_recently_healthy(-7) is False


def test_mark_runtime_cooldown_invalidates_healthy_cache():
    mark_healthy(-9, ttl_seconds=60)
    assert is_recently_healthy(-9) is True

    mark_runtime_cooldown(-9, reason="test", cooldown_seconds=60)
    assert is_recently_healthy(-9) is False


def test_clear_healthy_removes_single_entry():
    mark_healthy(-11, ttl_seconds=60)
    mark_healthy(-12, ttl_seconds=60)
    clear_healthy(-11)
    assert is_recently_healthy(-11) is False
    assert is_recently_healthy(-12) is True


def test_clear_healthy_no_args_drops_all_entries():
    mark_healthy(-21, ttl_seconds=60)
    mark_healthy(-22, ttl_seconds=60)
    clear_healthy()
    assert is_recently_healthy(-21) is False
    assert is_recently_healthy(-22) is False
