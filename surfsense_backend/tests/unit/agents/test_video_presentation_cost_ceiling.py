"""The spend guard on the video pipeline.

Video generation runs in Celery, so it loads no agent middleware and
``RunCostLimitMiddleware`` never sees it. Its only bounds were the upfront
reserve — a hold, while settlement charges actual cost — and the retry limits.
One LLM call per slide with up to three refine retries each puts the worst case
at ``2 + 4N`` calls, which at the measured p99 background call cost of $0.028
is about $3.42 for a maxed-out video.

The refine loop is where that runs away, because every retry carries the whole
broken component plus the error, so these tests pin the abort to it.
"""

from __future__ import annotations

import pytest

from app.agents.video_presentation.nodes import (
    MAX_REFINE_ATTEMPTS,
    VideoCostCeilingError,
    _abort_if_over_cost_ceiling,
    _refine_if_needed,
)
from app.config import config
from app.services.token_tracking_service import scoped_turn

pytestmark = pytest.mark.unit


def _add_call(acc, cost_micros: int) -> None:
    acc.add(
        model="azure/gpt-5.4",
        prompt_tokens=1000,
        completion_tokens=100,
        total_tokens=1100,
        cost_micros=cost_micros,
    )


class _CountingLLM:
    """Returns code that never passes the syntax check, so refine keeps going."""

    def __init__(self) -> None:
        self.calls = 0

    async def ainvoke(self, _messages):
        self.calls += 1

        class _Response:
            content = "this is not a remotion component"

        return _Response()


@pytest.mark.asyncio
async def test_a_cheap_run_is_left_alone() -> None:
    async with scoped_turn() as acc:
        _add_call(acc, 40_000)  # $0.04, a typical 9-slide video
        _abort_if_over_cost_ceiling("scene generation")


@pytest.mark.asyncio
async def test_crossing_the_ceiling_aborts_the_run() -> None:
    async with scoped_turn() as acc:
        acc.max_run_cost_micros = 250_000
        _add_call(acc, 250_000)
        with pytest.raises(VideoCostCeilingError):
            _abort_if_over_cost_ceiling("scene generation")


@pytest.mark.asyncio
async def test_the_plan_ceiling_wins_over_the_default() -> None:
    """A free user gets a quarter of the paid ceiling. Without this the guard
    would let one video eat their entire $1 month."""
    free_ceiling = config.AGENT_MAX_RUN_COST_MICROS_FREE
    async with scoped_turn() as acc:
        acc.max_run_cost_micros = free_ceiling
        _add_call(acc, free_ceiling)
        assert acc.total_cost_micros < config.AGENT_MAX_RUN_COST_MICROS, (
            "the test is only meaningful below the paid ceiling"
        )
        with pytest.raises(VideoCostCeilingError):
            _abort_if_over_cost_ceiling("scene generation")


@pytest.mark.asyncio
async def test_an_unmetered_run_fails_open() -> None:
    """No accumulator means nothing is metering this — a unit test, or a path
    that opened no billable envelope. This bounds spend, it does not authorize,
    so it must not break generation when it cannot see the cost."""
    _abort_if_over_cost_ceiling("scene generation")


@pytest.mark.asyncio
async def test_the_refine_loop_stops_burning_calls_once_over_budget() -> None:
    """The regression that motivated the guard: 30 slides each retrying three
    times is 90 extra calls, every one carrying the full broken component."""
    llm = _CountingLLM()
    async with scoped_turn() as acc:
        acc.max_run_cost_micros = 250_000
        _add_call(acc, 250_000)
        with pytest.raises(VideoCostCeilingError):
            await _refine_if_needed(llm, "not valid code", slide_number=1)

    assert llm.calls == 0, "must not spend another call after the ceiling"


@pytest.mark.asyncio
async def test_refinement_still_exhausts_its_attempts_when_affordable() -> None:
    """The guard must not shorten the retry budget of a run that can pay for
    it, or a fixable slide would start failing."""
    llm = _CountingLLM()
    async with scoped_turn() as acc:
        acc.max_run_cost_micros = 1_000_000
        _add_call(acc, 1_000)
        with pytest.raises(RuntimeError) as excinfo:
            await _refine_if_needed(llm, "not valid code", slide_number=1)

    assert not isinstance(excinfo.value, VideoCostCeilingError)
    assert llm.calls == MAX_REFINE_ATTEMPTS


def test_the_slide_cap_bounds_the_worst_case_call_count() -> None:
    """Measured over 180 days and 228 videos: mean 9 slides, p90 17, max 30.
    The cap has to sit above p90 or it truncates ordinary videos."""
    cap = config.VIDEO_PRESENTATION_MAX_SLIDES
    assert cap >= 17, "would truncate the p90 video"
    worst_case_calls = 2 + cap * (1 + MAX_REFINE_ATTEMPTS)
    assert worst_case_calls <= 82, "worst-case fan-out regressed"
