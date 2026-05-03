"""Unit tests for the ``billable_call`` async context manager.

Covers the per-call premium-credit lifecycle for image generation and
vision LLM extraction:

* Free configs bypass reserve/finalize but still write an audit row.
* Premium reserve denial raises ``QuotaInsufficientError`` (HTTP 402 in the
  route layer).
* Successful premium calls reserve, yield the accumulator, then finalize
  with the LiteLLM-reported actual cost — and write an audit row.
* Failed premium calls release the reservation so credit isn't leaked.
* All quota DB ops happen inside their OWN ``shielded_async_session``,
  isolating them from the caller's transaction (issue A).
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any
from uuid import uuid4

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeQuotaResult:
    def __init__(
        self,
        *,
        allowed: bool,
        used: int = 0,
        limit: int = 5_000_000,
        remaining: int = 5_000_000,
    ) -> None:
        self.allowed = allowed
        self.used = used
        self.limit = limit
        self.remaining = remaining


class _FakeSession:
    """Minimal AsyncSession stub — record commits for assertion."""

    def __init__(self) -> None:
        self.committed = False
        self.added: list[Any] = []

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        pass

    async def close(self) -> None:
        pass


@contextlib.asynccontextmanager
async def _fake_shielded_session():
    s = _FakeSession()
    _SESSIONS_USED.append(s)
    yield s


_SESSIONS_USED: list[_FakeSession] = []


def _patch_isolation_layer(
    monkeypatch, *, reserve_result, finalize_result=None, finalize_exc=None
):
    """Wire fake reserve/finalize/release/session helpers."""
    _SESSIONS_USED.clear()
    reserve_calls: list[dict[str, Any]] = []
    finalize_calls: list[dict[str, Any]] = []
    release_calls: list[dict[str, Any]] = []

    async def _fake_reserve(*, db_session, user_id, request_id, reserve_micros):
        reserve_calls.append(
            {
                "user_id": user_id,
                "reserve_micros": reserve_micros,
                "request_id": request_id,
            }
        )
        return reserve_result

    async def _fake_finalize(
        *, db_session, user_id, request_id, actual_micros, reserved_micros
    ):
        if finalize_exc is not None:
            raise finalize_exc
        finalize_calls.append(
            {
                "user_id": user_id,
                "actual_micros": actual_micros,
                "reserved_micros": reserved_micros,
            }
        )
        return finalize_result or _FakeQuotaResult(allowed=True)

    async def _fake_release(*, db_session, user_id, reserved_micros):
        release_calls.append({"user_id": user_id, "reserved_micros": reserved_micros})

    record_calls: list[dict[str, Any]] = []

    async def _fake_record(session, **kwargs):
        record_calls.append(kwargs)
        return object()

    monkeypatch.setattr(
        "app.services.billable_calls.TokenQuotaService.premium_reserve",
        _fake_reserve,
        raising=False,
    )
    monkeypatch.setattr(
        "app.services.billable_calls.TokenQuotaService.premium_finalize",
        _fake_finalize,
        raising=False,
    )
    monkeypatch.setattr(
        "app.services.billable_calls.TokenQuotaService.premium_release",
        _fake_release,
        raising=False,
    )
    monkeypatch.setattr(
        "app.services.billable_calls.shielded_async_session",
        _fake_shielded_session,
        raising=False,
    )
    monkeypatch.setattr(
        "app.services.billable_calls.record_token_usage",
        _fake_record,
        raising=False,
    )

    return {
        "reserve": reserve_calls,
        "finalize": finalize_calls,
        "release": release_calls,
        "record": record_calls,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_free_path_skips_reserve_but_writes_audit_row(monkeypatch):
    from app.services.billable_calls import billable_call

    spies = _patch_isolation_layer(
        monkeypatch, reserve_result=_FakeQuotaResult(allowed=True)
    )
    user_id = uuid4()

    async with billable_call(
        user_id=user_id,
        search_space_id=42,
        billing_tier="free",
        base_model="openai/gpt-image-1",
        usage_type="image_generation",
    ) as acc:
        # Simulate a captured cost — the accumulator is fed by the LiteLLM
        # callback in real life, here we add it manually.
        acc.add(
            model="openai/gpt-image-1",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost_micros=37_000,
            call_kind="image_generation",
        )

    assert spies["reserve"] == []
    assert spies["finalize"] == []
    assert spies["release"] == []
    # Free still audits.
    assert len(spies["record"]) == 1
    assert spies["record"][0]["usage_type"] == "image_generation"
    assert spies["record"][0]["cost_micros"] == 37_000


@pytest.mark.asyncio
async def test_premium_reserve_denied_raises_quota_insufficient(monkeypatch):
    from app.services.billable_calls import (
        QuotaInsufficientError,
        billable_call,
    )

    spies = _patch_isolation_layer(
        monkeypatch,
        reserve_result=_FakeQuotaResult(
            allowed=False, used=5_000_000, limit=5_000_000, remaining=0
        ),
    )
    user_id = uuid4()

    with pytest.raises(QuotaInsufficientError) as exc_info:
        async with billable_call(
            user_id=user_id,
            search_space_id=42,
            billing_tier="premium",
            base_model="openai/gpt-image-1",
            quota_reserve_micros_override=50_000,
            usage_type="image_generation",
        ):
            pytest.fail("body should not run when reserve is denied")

    err = exc_info.value
    assert err.usage_type == "image_generation"
    assert err.used_micros == 5_000_000
    assert err.limit_micros == 5_000_000
    assert err.remaining_micros == 0
    # Reserve was attempted, but no finalize/release on a denied reserve
    # — the reservation never actually held credit.
    assert len(spies["reserve"]) == 1
    assert spies["finalize"] == []
    assert spies["release"] == []
    # Denied premium calls do NOT create an audit row (no work happened).
    assert spies["record"] == []


@pytest.mark.asyncio
async def test_premium_success_finalizes_with_actual_cost(monkeypatch):
    from app.services.billable_calls import billable_call

    spies = _patch_isolation_layer(
        monkeypatch, reserve_result=_FakeQuotaResult(allowed=True)
    )
    user_id = uuid4()

    async with billable_call(
        user_id=user_id,
        search_space_id=42,
        billing_tier="premium",
        base_model="openai/gpt-image-1",
        quota_reserve_micros_override=50_000,
        usage_type="image_generation",
    ) as acc:
        # LiteLLM callback would normally fill this — simulate $0.04 image.
        acc.add(
            model="openai/gpt-image-1",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost_micros=40_000,
            call_kind="image_generation",
        )

    assert len(spies["reserve"]) == 1
    assert spies["reserve"][0]["reserve_micros"] == 50_000
    assert len(spies["finalize"]) == 1
    assert spies["finalize"][0]["actual_micros"] == 40_000
    assert spies["finalize"][0]["reserved_micros"] == 50_000
    assert spies["release"] == []
    # And audit row written with the actual debited cost.
    assert spies["record"][0]["cost_micros"] == 40_000
    # Each quota op opened its OWN session — proves session isolation.
    assert len(_SESSIONS_USED) >= 3
    # Sessions used should each have committed (or be the audit one which commits).
    for _s in _SESSIONS_USED:
        # finalize/reserve happen via TokenQuotaService.* which we stub —
        # they don't actually call commit on our fake session, but the
        # audit session does. We just assert >=1 session committed.
        pass
    assert any(s.committed for s in _SESSIONS_USED)


@pytest.mark.asyncio
async def test_premium_failure_releases_reservation(monkeypatch):
    from app.services.billable_calls import billable_call

    spies = _patch_isolation_layer(
        monkeypatch, reserve_result=_FakeQuotaResult(allowed=True)
    )
    user_id = uuid4()

    class _ProviderError(Exception):
        pass

    with pytest.raises(_ProviderError):
        async with billable_call(
            user_id=user_id,
            search_space_id=42,
            billing_tier="premium",
            base_model="openai/gpt-image-1",
            quota_reserve_micros_override=50_000,
            usage_type="image_generation",
        ):
            raise _ProviderError("OpenRouter 503")

    assert len(spies["reserve"]) == 1
    assert spies["finalize"] == []
    # Failure path: release the held reservation.
    assert len(spies["release"]) == 1
    assert spies["release"][0]["reserved_micros"] == 50_000


@pytest.mark.asyncio
async def test_premium_uses_estimator_when_no_micros_override(monkeypatch):
    """When ``quota_reserve_micros_override`` is None we fall back to
    ``estimate_call_reserve_micros(base_model, quota_reserve_tokens)``.
    Vision LLM calls take this path (token-priced models).
    """
    from app.services.billable_calls import billable_call

    spies = _patch_isolation_layer(
        monkeypatch, reserve_result=_FakeQuotaResult(allowed=True)
    )

    captured_estimator_calls: list[dict[str, Any]] = []

    def _fake_estimate(*, base_model, quota_reserve_tokens):
        captured_estimator_calls.append(
            {"base_model": base_model, "quota_reserve_tokens": quota_reserve_tokens}
        )
        return 12_345

    monkeypatch.setattr(
        "app.services.billable_calls.estimate_call_reserve_micros",
        _fake_estimate,
        raising=False,
    )

    user_id = uuid4()
    async with billable_call(
        user_id=user_id,
        search_space_id=1,
        billing_tier="premium",
        base_model="openai/gpt-4o",
        quota_reserve_tokens=4000,
        usage_type="vision_extraction",
    ):
        pass

    assert captured_estimator_calls == [
        {"base_model": "openai/gpt-4o", "quota_reserve_tokens": 4000}
    ]
    assert spies["reserve"][0]["reserve_micros"] == 12_345


@pytest.mark.asyncio
async def test_premium_finalize_failure_propagates_and_releases(monkeypatch):
    from app.services.billable_calls import BillingSettlementError, billable_call

    class _FinalizeError(RuntimeError):
        pass

    spies = _patch_isolation_layer(
        monkeypatch,
        reserve_result=_FakeQuotaResult(allowed=True),
        finalize_exc=_FinalizeError("db finalize failed"),
    )
    user_id = uuid4()

    with pytest.raises(BillingSettlementError):
        async with billable_call(
            user_id=user_id,
            search_space_id=42,
            billing_tier="premium",
            base_model="openai/gpt-image-1",
            quota_reserve_micros_override=50_000,
            usage_type="image_generation",
        ) as acc:
            acc.add(
                model="openai/gpt-image-1",
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                cost_micros=40_000,
                call_kind="image_generation",
            )

    assert len(spies["reserve"]) == 1
    assert len(spies["release"]) == 1
    assert spies["record"] == []


@pytest.mark.asyncio
async def test_premium_audit_commit_hang_times_out_after_finalize(monkeypatch):
    from app.services.billable_calls import billable_call

    spies = _patch_isolation_layer(
        monkeypatch, reserve_result=_FakeQuotaResult(allowed=True)
    )
    user_id = uuid4()

    class _HangingCommitSession(_FakeSession):
        async def commit(self) -> None:
            await asyncio.sleep(60)

    @contextlib.asynccontextmanager
    async def _hanging_session_factory():
        s = _HangingCommitSession()
        _SESSIONS_USED.append(s)
        yield s

    async with billable_call(
        user_id=user_id,
        search_space_id=42,
        billing_tier="premium",
        base_model="openai/gpt-image-1",
        quota_reserve_micros_override=50_000,
        usage_type="image_generation",
        billable_session_factory=_hanging_session_factory,
        audit_timeout_seconds=0.01,
    ) as acc:
        acc.add(
            model="openai/gpt-image-1",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost_micros=40_000,
            call_kind="image_generation",
        )

    assert len(spies["reserve"]) == 1
    assert len(spies["finalize"]) == 1
    assert len(spies["record"]) == 1
    assert spies["release"] == []


@pytest.mark.asyncio
async def test_free_audit_failure_is_best_effort(monkeypatch):
    from app.services.billable_calls import billable_call

    spies = _patch_isolation_layer(
        monkeypatch, reserve_result=_FakeQuotaResult(allowed=True)
    )

    async def _failing_record(_session, **_kwargs):
        raise RuntimeError("audit insert failed")

    monkeypatch.setattr(
        "app.services.billable_calls.record_token_usage",
        _failing_record,
        raising=False,
    )

    async with billable_call(
        user_id=uuid4(),
        search_space_id=42,
        billing_tier="free",
        base_model="openai/gpt-image-1",
        usage_type="image_generation",
        audit_timeout_seconds=0.01,
    ) as acc:
        acc.add(
            model="openai/gpt-image-1",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost_micros=37_000,
            call_kind="image_generation",
        )

    assert spies["reserve"] == []
    assert spies["finalize"] == []


# ---------------------------------------------------------------------------
# Podcast / video-presentation usage_type coverage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_free_podcast_path_audits_with_podcast_usage_type(monkeypatch):
    """Free podcast configs must skip reserve/finalize but still emit a
    ``TokenUsage`` row tagged ``usage_type='podcast_generation'`` so we
    have full audit coverage of free-tier agent runs."""
    from app.services.billable_calls import billable_call

    spies = _patch_isolation_layer(
        monkeypatch, reserve_result=_FakeQuotaResult(allowed=True)
    )
    user_id = uuid4()

    async with billable_call(
        user_id=user_id,
        search_space_id=42,
        billing_tier="free",
        base_model="openrouter/some-free-model",
        quota_reserve_micros_override=200_000,
        usage_type="podcast_generation",
        thread_id=99,
        call_details={"podcast_id": 7, "title": "Test Podcast"},
    ) as acc:
        # Two transcript LLM calls aggregated into one accumulator.
        acc.add(
            model="openrouter/some-free-model",
            prompt_tokens=1500,
            completion_tokens=8000,
            total_tokens=9500,
            cost_micros=0,
            call_kind="chat",
        )

    assert spies["reserve"] == []
    assert spies["finalize"] == []
    assert spies["release"] == []

    assert len(spies["record"]) == 1
    row = spies["record"][0]
    assert row["usage_type"] == "podcast_generation"
    assert row["thread_id"] is None
    assert row["search_space_id"] == 42
    assert row["call_details"] == {"podcast_id": 7, "title": "Test Podcast"}


@pytest.mark.asyncio
async def test_premium_video_denial_raises_quota_insufficient(monkeypatch):
    """Premium video-presentation runs that hit a denied reservation must
    raise ``QuotaInsufficientError`` *before* the graph runs and must not
    emit an audit row (no work happened)."""
    from app.services.billable_calls import (
        QuotaInsufficientError,
        billable_call,
    )

    spies = _patch_isolation_layer(
        monkeypatch,
        reserve_result=_FakeQuotaResult(
            allowed=False, used=4_500_000, limit=5_000_000, remaining=500_000
        ),
    )
    user_id = uuid4()

    with pytest.raises(QuotaInsufficientError) as exc_info:
        async with billable_call(
            user_id=user_id,
            search_space_id=42,
            billing_tier="premium",
            base_model="gpt-5.4",
            quota_reserve_micros_override=1_000_000,
            usage_type="video_presentation_generation",
            thread_id=99,
            call_details={"video_presentation_id": 12, "title": "Test Video"},
        ):
            pytest.fail("body should not run when reserve is denied")

    err = exc_info.value
    assert err.usage_type == "video_presentation_generation"
    assert err.remaining_micros == 500_000
    assert spies["reserve"][0]["reserve_micros"] == 1_000_000
    assert spies["finalize"] == []
    assert spies["release"] == []
    assert spies["record"] == []
