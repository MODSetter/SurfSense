"""Offline resilience tests for the fetch seam and fan-out worker pool.

No network. Stubs the proxy session so the rotate-on-block path (which never
fires in practice because live runs return 200s) is exercised deterministically,
and asserts the worker pool closes every session when the consumer stops early.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from app.proprietary.platforms.youtube import innertube, scraper
from app.proprietary.platforms.youtube.innertube import (
    INNERTUBE_SEARCH_URL,
    _current_session,
    fetch_html,
    post_innertube,
)


class _FakePage:
    def __init__(self, status: int) -> None:
        self.status = status

    def json(self) -> dict:
        return {"status": self.status}

    @property
    def html_content(self) -> str:
        return "<html>ok</html>"


class _FakeSession:
    """One 'IP': returns ``status`` for every request, or raises if ``exc``."""

    def __init__(self, status: int = 200, *, exc: bool = False) -> None:
        self.status = status
        self.exc = exc
        self.calls = 0

    async def post(self, url, json=None):
        self.calls += 1
        if self.exc:
            raise ConnectionError("boom")
        return _FakePage(self.status)

    async def get(self, url, headers=None, cookies=None):
        self.calls += 1
        if self.exc:
            raise ConnectionError("boom")
        return _FakePage(self.status)


class _FakeHolder:
    """Holder whose ``rotate()`` advances to the next fake session (a new IP)."""

    def __init__(self, sessions: list[_FakeSession]) -> None:
        self._sessions = sessions
        self.session = sessions[0]
        self.rotations = 0

    async def rotate(self):
        self.rotations += 1
        self.session = self._sessions[min(self.rotations, len(self._sessions) - 1)]
        return self.session


def _payload() -> dict:
    return {"context": {}}


async def test_post_rotates_on_429_then_succeeds():
    holder = _FakeHolder([_FakeSession(429), _FakeSession(200)])
    token = _current_session.set(holder)
    try:
        result = await post_innertube(INNERTUBE_SEARCH_URL, _payload())
    finally:
        _current_session.reset(token)
    assert result == {"status": 200}
    assert holder.rotations == 1  # rotated exactly once to the healthy IP


async def test_post_rotates_on_connection_error_then_succeeds():
    holder = _FakeHolder([_FakeSession(exc=True), _FakeSession(200)])
    token = _current_session.set(holder)
    try:
        result = await post_innertube(INNERTUBE_SEARCH_URL, _payload())
    finally:
        _current_session.reset(token)
    assert result == {"status": 200}
    assert holder.rotations == 1


async def test_post_gives_up_after_max_rotations():
    # Every IP is blocked -> rotate up to the cap, then return None.
    holder = _FakeHolder([_FakeSession(429) for _ in range(innertube._MAX_ROTATIONS + 1)])
    token = _current_session.set(holder)
    try:
        result = await post_innertube(INNERTUBE_SEARCH_URL, _payload())
    finally:
        _current_session.reset(token)
    assert result is None
    assert holder.rotations == innertube._MAX_ROTATIONS


async def test_post_does_not_rotate_on_non_block_status():
    # 404 is not a block: fail fast, no wasted IP rotations.
    holder = _FakeHolder([_FakeSession(404), _FakeSession(200)])
    token = _current_session.set(holder)
    try:
        result = await post_innertube(INNERTUBE_SEARCH_URL, _payload())
    finally:
        _current_session.reset(token)
    assert result is None
    assert holder.rotations == 0


async def test_fetch_html_rotates_then_succeeds():
    holder = _FakeHolder([_FakeSession(403), _FakeSession(200)])
    token = _current_session.set(holder)
    try:
        html = await fetch_html("https://www.youtube.com/watch?v=abc")
    finally:
        _current_session.reset(token)
    assert html == "<html>ok</html>"
    assert holder.rotations == 1


async def test_fetch_html_falls_back_to_stealthy_when_all_blocked(monkeypatch):
    called: dict[str, str] = {}

    async def _fake_stealthy(url: str):
        called["url"] = url
        return "<html>stealthy</html>"

    monkeypatch.setattr(innertube, "_fetch_html_stealthy", _fake_stealthy)
    holder = _FakeHolder([_FakeSession(429) for _ in range(innertube._MAX_ROTATIONS + 1)])
    token = _current_session.set(holder)
    try:
        html = await fetch_html("https://www.youtube.com/watch?v=zzz")
    finally:
        _current_session.reset(token)
    assert html == "<html>stealthy</html>"
    assert called["url"].endswith("v=zzz")


class _TrackingHolder:
    """Fake fan-out session holder that records whether it was closed."""

    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


async def test_fan_out_closes_all_sessions_on_early_stop(monkeypatch):
    holders: list[_TrackingHolder] = []

    async def _fake_open():
        h = _TrackingHolder()
        holders.append(h)
        return h

    # No real session binding needed; jobs just yield.
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _fake_bind(_holder):
        yield _holder

    monkeypatch.setattr(scraper, "open_proxy_holder", _fake_open)
    monkeypatch.setattr(scraper, "bind_proxy_holder", _fake_bind)

    async def _job(n: int) -> AsyncIterator[dict]:
        for i in range(5):
            yield {"job": n, "i": i}

    jobs = [_job(n) for n in range(20)]

    gen = scraper.fan_out(jobs, concurrency=4)
    collected = []
    async for item in gen:
        collected.append(item)
        if len(collected) >= 3:  # consumer stops early (like a limit)
            break
    await gen.aclose()  # deterministically run fan_out's teardown

    assert len(collected) >= 3
    assert holders, "workers should have opened sessions"
    # Every opened session must be closed after the generator is torn down.
    assert all(h.closed for h in holders), "a worker leaked its proxy session"


async def test_fan_out_empty_jobs_is_noop():
    out = [x async for x in scraper.fan_out([])]
    assert out == []
