"""A thread from opencode 1.x, read while 2.x is still importing its session."""

import httpx
import pytest

from modules.agent.agent_threads import session_import
from modules.agent.agent_threads.session_import import (
    found_after_import,
    note_serving,
)

pytestmark = pytest.mark.unit


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class _Opencode:
    """A server with its pid, whose session answers 404 `missing` times first."""

    def __init__(self, pid: int, missing: int) -> None:
        self.pid = pid
        self.missing = missing
        self.asked = 0

    async def server_pid(self) -> int:
        return self.pid

    async def look(self) -> str:
        self.asked += 1
        if self.asked <= self.missing:
            request = httpx.Request("GET", "http://opencode/api/session/ses_1")
            raise httpx.HTTPStatusError(
                "gone", request=request, response=httpx.Response(404, request=request)
            )
        return "C:/threads/7"


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> _Clock:
    """Time this module reads, moved on by each wait instead of waiting."""
    clock = _Clock()
    monkeypatch.setattr(session_import, "_now", clock)
    monkeypatch.setattr(session_import, "_seen", {})

    async def no_wait(_seconds: float) -> None:
        clock.now += 0.25

    monkeypatch.setattr(session_import.asyncio, "sleep", no_wait)
    return clock


async def test_a_session_still_being_imported_is_found_once_it_is(
    clock: _Clock,
) -> None:
    """2.x imports 1.x's sessions on its first start; until then each answers 404."""
    opencode = _Opencode(pid=42, missing=3)
    note_serving(42)

    assert await found_after_import(opencode, opencode.look) == "C:/threads/7"
    assert opencode.asked == 4


async def test_a_session_missing_long_after_the_start_is_gone_at_once(
    clock: _Clock,
) -> None:
    """A thread whose session was deleted must not wait to say so."""
    opencode = _Opencode(pid=42, missing=99)
    note_serving(42)
    clock.now += session_import.IMPORT_SECONDS + 1

    with pytest.raises(httpx.HTTPStatusError):
        await found_after_import(opencode, opencode.look)
    assert opencode.asked == 1


async def test_a_server_never_seen_starting_is_not_waited_on(clock: _Clock) -> None:
    """Only a start this API saw can still be importing."""
    opencode = _Opencode(pid=7, missing=99)

    with pytest.raises(httpx.HTTPStatusError):
        await found_after_import(opencode, opencode.look)
    assert opencode.asked == 1


async def test_the_wait_ends_when_the_import_would_have(clock: _Clock) -> None:
    """A session never imported is gone once the import would have ended."""
    opencode = _Opencode(pid=42, missing=10_000)
    note_serving(42)

    with pytest.raises(httpx.HTTPStatusError):
        await found_after_import(opencode, opencode.look)
    assert clock.now <= 1000.0 + session_import.IMPORT_SECONDS + 0.5
