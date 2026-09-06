"""Tests for RunCostLimitMiddleware, the settled-cost ceiling on an agent run.

The gap this guards is real: on production traffic the worst single turn
settled at $21.44 across 8.04M tokens while staying inside the 80-call
``ModelCallLimitMiddleware`` budget, because that limit counts calls and not
the context stuffed into each one.
"""

from __future__ import annotations

import pytest

from app.agents.chat.multi_agent_chat.shared.middleware.resilience.run_cost_limit import (
    RunCostLimitMiddleware,
    build_run_cost_limit_mw,
)
from app.services.token_tracking_service import scoped_turn

pytestmark = pytest.mark.unit


class _FakeRuntime:
    """Stand-in for ``langgraph.runtime.Runtime``; the middleware ignores it."""

    def __init__(self) -> None:
        self.config = {"configurable": {"thread_id": "thread-1"}}


def _add_call(acc, cost_micros: int) -> None:
    acc.add(
        model="azure/gpt-5.4",
        prompt_tokens=1000,
        completion_tokens=100,
        total_tokens=1100,
        cost_micros=cost_micros,
    )


@pytest.mark.asyncio
async def test_under_ceiling_lets_the_run_continue() -> None:
    mw = RunCostLimitMiddleware(max_cost_micros=500_000)
    async with scoped_turn() as acc:
        _add_call(acc, 100_000)
        _add_call(acc, 200_000)
        assert mw.after_model({"messages": []}, _FakeRuntime()) is None


@pytest.mark.asyncio
async def test_crossing_ceiling_ends_the_run() -> None:
    mw = RunCostLimitMiddleware(max_cost_micros=500_000)
    async with scoped_turn() as acc:
        _add_call(acc, 400_000)
        assert mw.after_model({"messages": []}, _FakeRuntime()) is None
        # One more call tips the turn over the ceiling.
        _add_call(acc, 150_000)
        assert mw.after_model({"messages": []}, _FakeRuntime()) == {"jump_to": "end"}


@pytest.mark.asyncio
async def test_ceiling_is_exclusive_at_the_boundary() -> None:
    """Exactly at the ceiling counts as crossed, so the guard cannot be sat on."""
    mw = RunCostLimitMiddleware(max_cost_micros=500_000)
    async with scoped_turn() as acc:
        _add_call(acc, 500_000)
        assert mw.after_model({"messages": []}, _FakeRuntime()) == {"jump_to": "end"}


@pytest.mark.asyncio
async def test_one_expensive_call_is_caught_despite_low_call_count() -> None:
    """The production failure mode: 1 call, huge context, well inside 80 calls."""
    mw = RunCostLimitMiddleware(max_cost_micros=500_000)
    async with scoped_turn() as acc:
        acc.add(
            model="azure/gpt-5.1",
            prompt_tokens=8_040_791,
            completion_tokens=2_000,
            total_tokens=8_042_791,
            cost_micros=21_440_000,  # $21.44
        )
        assert len(acc.calls) == 1
        assert mw.after_model({"messages": []}, _FakeRuntime()) == {"jump_to": "end"}


@pytest.mark.asyncio
async def test_ending_a_run_flags_the_turn_for_the_user() -> None:
    """Without this the user just gets a half-answer and no reason for it."""
    mw = RunCostLimitMiddleware(max_cost_micros=500_000)
    async with scoped_turn() as acc:
        _add_call(acc, 100_000)
        mw.after_model({"messages": []}, _FakeRuntime())
        assert acc.cost_limited is False

        _add_call(acc, 500_000)
        mw.after_model({"messages": []}, _FakeRuntime())
        assert acc.cost_limited is True


@pytest.mark.asyncio
async def test_turn_ceiling_overrides_the_constructed_default() -> None:
    """A free plan's lower ceiling reaches the middleware via the accumulator.

    The middleware instance is shared across the whole turn and built long
    before the user is known, so the per-plan number can only arrive this way.
    """
    mw = RunCostLimitMiddleware(max_cost_micros=1_000_000)
    async with scoped_turn() as acc:
        acc.max_run_cost_micros = 250_000
        _add_call(acc, 300_000)
        # Under the constructed $1.00 default this run would have continued.
        assert mw.after_model({"messages": []}, _FakeRuntime()) == {"jump_to": "end"}


@pytest.mark.asyncio
async def test_unset_turn_ceiling_falls_back_to_the_default() -> None:
    mw = RunCostLimitMiddleware(max_cost_micros=1_000_000)
    async with scoped_turn() as acc:
        assert acc.max_run_cost_micros is None
        _add_call(acc, 300_000)
        assert mw.after_model({"messages": []}, _FakeRuntime()) is None


def test_free_plan_resolves_to_a_lower_ceiling_than_paid() -> None:
    from app.config import config

    free = config.run_cost_ceiling_micros("free")
    assert free < config.run_cost_ceiling_micros("pro")
    # An unrecognised plan must not be throttled to the free ceiling — that
    # would silently degrade paying users during a bad deploy.
    assert config.run_cost_ceiling_micros("enterprise_v2") > free
    assert config.run_cost_ceiling_micros(None) > free


@pytest.mark.asyncio
async def test_async_hook_matches_sync_hook() -> None:
    mw = RunCostLimitMiddleware(max_cost_micros=500_000)
    async with scoped_turn() as acc:
        _add_call(acc, 600_000)
        assert await mw.aafter_model({"messages": []}, _FakeRuntime()) == {
            "jump_to": "end"
        }


def test_no_accumulator_fails_open() -> None:
    """Outside a metered turn there is nothing to bound; must not end the run."""
    mw = RunCostLimitMiddleware(max_cost_micros=500_000)
    assert mw.after_model({"messages": []}, _FakeRuntime()) is None


def test_non_positive_ceiling_is_rejected() -> None:
    with pytest.raises(ValueError):
        RunCostLimitMiddleware(max_cost_micros=0)


def test_builder_returns_none_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import config

    monkeypatch.setattr(config, "AGENT_MAX_RUN_COST_MICROS", 0, raising=False)
    assert build_run_cost_limit_mw() is None


def test_builder_uses_configured_ceiling(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import config

    monkeypatch.setattr(config, "AGENT_MAX_RUN_COST_MICROS", 250_000, raising=False)
    mw = build_run_cost_limit_mw()
    assert mw is not None
    assert mw._max_cost_micros == 250_000
