"""Progress at each stage of a call: once a second at most, always rising, never failing."""

import asyncio
import threading
from collections.abc import Iterator
from typing import Any

import pytest
from mcp.server.mcpserver import Context

from mcp_server import progress
from mcp_server.progress import stage


class Heard:
    """A context that keeps each notification it is asked to send."""

    def __init__(self) -> None:
        self.sent: list[tuple[float, float | None, str | None]] = []
        self.loops: list[asyncio.AbstractEventLoop] = []

    async def report_progress(
        self, value: float, total: float | None = None, message: str | None = None
    ) -> None:
        self.sent.append((value, total, message))
        self.loops.append(asyncio.get_running_loop())


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Iterator[Clock]:
    moved = Clock()
    monkeypatch.setattr(progress, "_clock", moved)
    yield moved


async def staged(ctx: Any, message: str, **counts: int | None) -> None:
    await stage(ctx, message, **counts)


async def test_at_most_one_notification_a_second(clock: Clock) -> None:
    ctx = Heard()
    await staged(ctx, "searching")
    clock.now += 0.5
    await staged(ctx, "page fetched")
    clock.now += 0.6
    await staged(ctx, "parsing")

    assert [message for _, _, message in ctx.sent] == ["searching", "parsing"]


async def test_the_value_rises_with_every_notification(clock: Clock) -> None:
    """MCP requires it, between items as at each one, and when an item repeats."""
    ctx = Heard()
    for message, done in [
        ("searching", None),
        ("page fetched", None),
        ("item", 1),
        ("page fetched", None),
        ("item again", 1),
        ("page fetched", None),
        ("item", 2),
    ]:
        await staged(ctx, message, done=done, total=3)
        clock.now += 1

    values = [value for value, _, _ in ctx.sent]
    assert len(values) == 7
    assert values == sorted(set(values))
    assert values[2] == 1
    assert values[-1] == 2
    assert all(total == 3 for _, total, _ in ctx.sent)


async def test_the_total_is_kept_once_given(clock: Clock) -> None:
    ctx = Heard()
    await staged(ctx, "searching", total=5)
    clock.now += 1
    await staged(ctx, "page fetched")

    assert [total for _, total, _ in ctx.sent] == [5, 5]


async def test_the_last_item_is_always_reported(clock: Clock) -> None:
    ctx = Heard()
    await staged(ctx, "searching", total=2)
    await staged(ctx, "item", done=1)
    await staged(ctx, "item", done=2)

    assert [(value, message) for value, _, message in ctx.sent] == [
        (0.5, "searching"),
        (2, "item"),
    ]


async def test_items_past_the_total_are_limited(clock: Clock) -> None:
    """A plugin may count past a per-URL total: only its first crossing is forced."""
    ctx = Heard()
    await staged(ctx, "searching", total=10)
    for count in range(1, 201):
        await staged(ctx, "item", done=count)

    assert [(value, message) for value, _, message in ctx.sent] == [
        (0.5, "searching"),
        (10, "item"),
    ]


async def test_each_call_is_limited_on_its_own(clock: Clock) -> None:
    first, second = Heard(), Heard()
    await staged(first, "searching")
    await staged(second, "searching")

    assert len(first.sent) == len(second.sent) == 1


async def test_a_stage_on_the_browser_loop_is_sent_on_the_call_s_own(
    clock: Clock,
) -> None:
    """The call's stream belongs to its loop; browser work runs on another."""
    ctx = Heard()
    await staged(ctx, "searching")
    clock.now += 1
    browser_loop = asyncio.new_event_loop()
    thread = threading.Thread(target=browser_loop.run_forever, daemon=True)
    thread.start()
    try:
        await asyncio.wrap_future(
            asyncio.run_coroutine_threadsafe(staged(ctx, "page fetched"), browser_loop)
        )
        for _ in range(50):
            if len(ctx.sent) == 2:
                break
            await asyncio.sleep(0.01)
    finally:
        browser_loop.call_soon_threadsafe(browser_loop.stop)
        thread.join()
        browser_loop.close()

    assert [message for _, _, message in ctx.sent] == ["searching", "page fetched"]
    assert ctx.loops == [asyncio.get_running_loop()] * 2


async def test_progress_never_fails_the_call(clock: Clock) -> None:
    class Gone:
        async def report_progress(self, *args: object) -> None:
            raise RuntimeError("the stream is closed")

    await staged(Gone(), "searching")
    await staged(Context(), "outside a request")
    await staged(None, "no context")
