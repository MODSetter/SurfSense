"""The shared pools close once, when the last plugin leaves, however its exit goes."""

from collections.abc import Awaitable, Callable

import anyio
import pytest

from proprietary.scraping import lifecycle


@pytest.fixture(autouse=True)
def fresh(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lifecycle, "_closers", [])
    monkeypatch.setattr(lifecycle, "_entered", 0)


class Pool:
    def __init__(self, closed: list[str], name: str) -> None:
        self.closed = closed
        self.name = name

    async def close(self) -> None:
        self.closed.append(self.name)


async def test_the_last_plugin_to_leave_closes_every_pool_once() -> None:
    closed: list[str] = []
    browsers, sessions = Pool(closed, "browsers"), Pool(closed, "sessions")
    async with lifecycle.lifespan():
        async with lifecycle.lifespan():
            lifecycle.at_shutdown(browsers.close)
            lifecycle.at_shutdown(sessions.close)
            lifecycle.at_shutdown(browsers.close)
        assert closed == []

    # In no set order: they close at once.
    assert sorted(closed) == ["browsers", "sessions"]


async def test_the_pools_close_at_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """One at a time, a few slow pools would outlast the container's stop grace."""
    monkeypatch.setattr(lifecycle, "CLOSE_SECONDS", 1.0)
    closed: list[str] = []
    started = {name: anyio.Event() for name in ("browsers", "sessions")}

    def waiting_for(name: str, other: str) -> Callable[[], Awaitable[None]]:
        async def close() -> None:
            # Ends only when the other pool's close has started too.
            started[name].set()
            await started[other].wait()
            closed.append(name)

        return close

    lifecycle.at_shutdown(waiting_for("browsers", "sessions"))
    lifecycle.at_shutdown(waiting_for("sessions", "browsers"))
    with anyio.fail_after(0.5):
        await lifecycle.close_all()

    assert sorted(closed) == ["browsers", "sessions"]
    assert lifecycle._closers == []


async def test_a_close_that_hangs_skips_none_of_the_others(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(lifecycle, "CLOSE_SECONDS", 0.1)
    closed: list[str] = []

    async def hangs() -> None:
        await anyio.sleep_forever()

    lifecycle.at_shutdown(Pool(closed, "browsers").close)
    lifecycle.at_shutdown(hangs)
    await lifecycle.close_all()

    assert closed == ["browsers"]


async def test_an_exit_cut_short_still_closes_the_pools() -> None:
    """The host cancels a plugin whose exit takes too long."""
    closed: list[str] = []

    async def slow_close() -> None:
        await anyio.sleep(0.05)
        closed.append("browsers")

    with anyio.CancelScope() as scope:
        async with lifecycle.lifespan():
            lifecycle.at_shutdown(slow_close)
            scope.cancel()
            await anyio.sleep(1)

    assert closed == ["browsers"]
