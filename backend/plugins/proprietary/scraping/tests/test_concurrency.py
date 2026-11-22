"""Ordered bounded fan-out and first-wins hedging: order, limits, cancellation."""

import asyncio
import gc
import logging
import time
from contextlib import aclosing, asynccontextmanager

import pytest

from proprietary.scraping import concurrency, sessions
from proprietary.scraping.concurrency import hedged, ordered_map
from proprietary.scraping.config import Config
from proprietary.scraping.http import HEDGE_INDEX
from proprietary.scraping.tests._local_http import LocalServer


@pytest.fixture(autouse=True)
def _hedging_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Config, "HEDGE", True)


class Tracker:
    """Records how many jobs run at once and how each one ended."""

    def __init__(self) -> None:
        self.running = 0
        self.peak = 0
        self.started: list[int] = []
        self.cancelled: list[int] = []
        self.finished: list[int] = []

    async def job(self, item: tuple[int, float]) -> int:
        index, delay = item
        self.started.append(index)
        self.running += 1
        self.peak = max(self.peak, self.running)
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            self.cancelled.append(index)
            raise
        finally:
            self.running -= 1
        self.finished.append(index)
        return index


@pytest.mark.asyncio
async def test_yields_in_input_order_whatever_finishes_first() -> None:
    t = Tracker()
    delays = [0.3, 0.05, 0.2, 0.01, 0.1]
    out = [r async for r in ordered_map(enumerate(delays), t.job, concurrency=5)]

    assert out == [0, 1, 2, 3, 4]
    assert t.finished != [0, 1, 2, 3, 4]  # they really did finish out of order


@pytest.mark.asyncio
async def test_never_runs_more_than_the_limit() -> None:
    t = Tracker()
    items = [(i, 0.02) for i in range(20)]
    out = [r async for r in ordered_map(items, t.job, concurrency=3)]

    assert out == list(range(20))
    assert t.peak == 3


@pytest.mark.asyncio
async def test_the_head_is_yielded_before_the_rest_finish() -> None:
    t = Tracker()
    items = [(0, 0.01), (1, 1.0)]
    started = time.monotonic()
    async with aclosing(ordered_map(items, t.job, concurrency=2)) as results:
        first = await anext(results)
        assert first == 0
        assert time.monotonic() - started < 0.5


@pytest.mark.asyncio
async def test_stopping_early_cancels_and_awaits_pending_jobs() -> None:
    t = Tracker()
    items = [(0, 0.01), (1, 5.0), (2, 5.0), (3, 5.0)]
    started = time.monotonic()
    async with aclosing(ordered_map(items, t.job, concurrency=2)) as results:
        async for r in results:
            assert r == 0
            break

    # aclosing returned only after the pending jobs ran their cancellation.
    assert sorted(t.cancelled) == [1, 2]
    assert t.running == 0
    assert 3 not in t.started
    assert time.monotonic() - started < 1


@pytest.mark.asyncio
async def test_a_bare_break_still_cancels_soon() -> None:
    t = Tracker()
    items = [(0, 0.01), (1, 5.0)]
    async for _ in ordered_map(items, t.job, concurrency=2):
        break
    gc.collect()
    await asyncio.sleep(0.1)

    assert t.cancelled == [1]


@pytest.mark.asyncio
async def test_cancelling_the_consumer_cancels_the_jobs() -> None:
    t = Tracker()
    items = [(i, 5.0) for i in range(4)]

    async def consume() -> list[int]:
        return [r async for r in ordered_map(items, t.job, concurrency=4)]

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert sorted(t.cancelled) == [0, 1, 2, 3]
    assert t.running == 0


@pytest.mark.asyncio
async def test_an_error_surfaces_in_order_and_stops_new_jobs() -> None:
    started: list[int] = []

    async def job(i: int) -> int:
        started.append(i)
        await asyncio.sleep(0.05 if i == 0 else 0.01)
        if i == 1:
            raise ValueError("boom")
        return i

    got: list[int] = []
    with pytest.raises(ValueError, match="boom"):
        async for r in ordered_map(range(10), job, concurrency=2):
            got.append(r)

    assert got == [0]  # what came before the failure is still delivered
    assert sorted(started) == [0, 1]  # nothing past the failure was started


@pytest.mark.asyncio
async def test_a_cancelled_error_from_a_job_fails_it_instead_of_ending_short() -> None:
    """fn lets a CancelledError out while nobody cancelled the map."""

    async def job(i: int) -> int:
        await asyncio.sleep(0.01 * i)
        if i == 2:
            future = asyncio.get_running_loop().create_future()
            future.cancel()
            await future
        return i

    got: list[int] = []
    with pytest.raises(RuntimeError, match="item 2"):
        async for r in ordered_map(range(6), job, concurrency=2):
            got.append(r)

    assert got == [0, 1]


@pytest.mark.asyncio
async def test_workers_stay_within_max_ahead_of_a_slow_head() -> None:
    t = Tracker()
    items = [(0, 0.3)] + [(i, 0.0) for i in range(1, 20)]
    async with aclosing(ordered_map(items, t.job, concurrency=2, max_ahead=4)) as rs:
        task = asyncio.create_task(anext(rs))
        await asyncio.sleep(0.15)
        assert sorted(t.started) == [0, 1, 2, 3]  # the head is still running
        assert await task == 0
        rest = [r async for r in rs]

    assert rest == list(range(1, 20))


@pytest.mark.asyncio
async def test_max_ahead_defaults_to_twice_the_concurrency() -> None:
    t = Tracker()
    items = [(0, 0.3)] + [(i, 0.0) for i in range(1, 30)]
    async with aclosing(ordered_map(items, t.job, concurrency=3)) as rs:
        task = asyncio.create_task(anext(rs))
        await asyncio.sleep(0.15)
        assert len(t.started) == 6
        assert await task == 0


@pytest.mark.asyncio
async def test_empty_input_and_lazy_iterables() -> None:
    async def double(i: int) -> int:
        return i * 2

    assert [r async for r in ordered_map([], double, concurrency=4)] == []
    lazy = (i for i in range(5))
    assert [r async for r in ordered_map(lazy, double, concurrency=2)] == [
        0,
        2,
        4,
        6,
        8,
    ]


@pytest.mark.asyncio
async def test_a_failing_items_iterator_surfaces() -> None:
    def items():
        yield 1
        raise KeyError("bad input")

    async def same(i: int) -> int:
        await asyncio.sleep(0.01)
        return i

    with pytest.raises(KeyError):
        _ = [r async for r in ordered_map(items(), same, concurrency=2)]


@pytest.mark.asyncio
async def test_each_worker_enters_its_context_once_and_jobs_see_its_holder() -> None:
    entered: list[int] = []

    @asynccontextmanager
    async def worker_context():
        entered.append(1)
        async with sessions.bound("test") as h:
            yield h

    async def job(i: int) -> int:
        await asyncio.sleep(0.01)
        h = sessions.current()
        assert h is not None
        return id(h)

    holders = [
        r
        async for r in ordered_map(
            range(12), job, concurrency=3, worker_context=worker_context
        )
    ]

    assert len(entered) == 3
    assert len(set(holders)) == 3
    assert sessions.live_sessions() == 0

    entered.clear()
    few = [
        r
        async for r in ordered_map(
            range(2), job, concurrency=8, worker_context=worker_context
        )
    ]
    assert len(few) == 2
    assert len(entered) == 2  # idle workers open nothing


@pytest.mark.asyncio
async def test_hedged_fast_first_attempt_starts_no_hedge() -> None:
    calls: list[int] = []

    async def attempt(i: int) -> str:
        calls.append(i)
        await asyncio.sleep(0.01)
        return f"r{i}"

    assert await hedged(attempt, after_s=0.2) == "r0"
    assert calls == [0]


@pytest.mark.asyncio
async def test_hedged_slow_first_attempt_loses_and_its_session_closes(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The first request served sleeps 5 s, like a slow exit; the hedge wins."""
    caplog.set_level(logging.INFO)
    async with LocalServer(slow_first_s=5.0) as server:

        async def attempt(i: int) -> tuple[int, int]:
            async with sessions.holder("test") as h:
                r = await h.request("GET", f"{server.base}/ok", stage="pdp")
                return i, r.status

        started = time.monotonic()
        winner = await hedged(attempt, after_s=0.3, plugin="test", stage="pdp")
        elapsed = time.monotonic() - started
        assert sessions.live_sessions() == 0  # the loser's holder closed already
        await asyncio.sleep(0.2)
        assert server.open_connections == 0  # and its socket really went away

    assert winner == (1, 200)
    assert elapsed < 2
    assert server.connections == 2
    perf = [m for m in caplog.messages if "[test][perf]" in m]
    assert any("hedge=1" in m and "status=200" in m for m in perf)
    assert any("stage=pdp hedge=1 winner=1" in m for m in perf)


@pytest.mark.asyncio
async def test_hedged_rejected_first_result_falls_back_without_a_retry() -> None:
    calls: list[int] = []

    async def attempt(i: int) -> int:
        calls.append(i)
        return 403

    result = await hedged(attempt, after_s=0.1, accept=lambda s: s == 200)

    assert result == 403
    assert calls == [0]  # the plugin's own rotation loop retries, not this


@pytest.mark.asyncio
async def test_hedged_accepts_a_later_attempt_over_a_rejected_one() -> None:
    async def attempt(i: int) -> int:
        await asyncio.sleep(0.4 if i == 0 else 0.05)
        return 403 if i == 0 else 200

    assert await hedged(attempt, after_s=0.1, accept=lambda s: s == 200) == 200


@pytest.mark.asyncio
async def test_hedged_raises_only_when_every_attempt_fails() -> None:
    async def attempt(i: int) -> int:
        await asyncio.sleep(0.2 if i == 0 else 0.05)
        raise ConnectionError(f"attempt {i}")

    with pytest.raises(ConnectionError, match="attempt 0"):
        await hedged(attempt, after_s=0.1)

    async def first_fails(i: int) -> int:
        await asyncio.sleep(0.2)
        if i == 0:
            raise ConnectionError("dead exit")
        return i

    assert await hedged(first_fails, after_s=0.1) == 1


@pytest.mark.asyncio
async def test_hedged_bounds_the_extra_attempts() -> None:
    t = Tracker()

    async def attempt(i: int) -> int:
        assert HEDGE_INDEX.get() == i
        return await t.job((i, 0.5))

    started = time.monotonic()
    assert await hedged(attempt, after_s=0.05, max_extra=2) == 0
    assert t.started == [0, 1, 2]
    assert sorted(t.cancelled) == [1, 2]
    assert time.monotonic() - started < 0.8


@pytest.mark.asyncio
async def test_a_hedge_runs_with_no_holder_bound() -> None:
    """Fetch helpers find their holder via current(); a hedge must not reuse it."""
    seen: dict[int, object] = {}

    async def attempt(i: int) -> int:
        seen[i] = sessions.current()
        await asyncio.sleep(0.3 if i == 0 else 0.01)
        return i

    async with sessions.bound("test") as h:
        assert await hedged(attempt, after_s=0.05) == 1
        assert sessions.current() is h

    assert seen == {0: h, 1: None}


@pytest.mark.asyncio
async def test_hedging_switched_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(concurrency.Config, "HEDGE", False)
    calls: list[int] = []

    async def attempt(i: int) -> int:
        calls.append(i)
        await asyncio.sleep(0.2)
        return i

    assert await hedged(attempt, after_s=0.05) == 0
    assert calls == [0]


@pytest.mark.asyncio
async def test_cancelling_hedged_cancels_every_attempt() -> None:
    t = Tracker()

    async def attempt(i: int) -> int:
        return await t.job((i, 5.0))

    task = asyncio.create_task(hedged(attempt, after_s=0.05))
    await asyncio.sleep(0.2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert sorted(t.cancelled) == [0, 1]
