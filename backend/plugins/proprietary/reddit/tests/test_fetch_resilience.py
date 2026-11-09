"""Offline resilience tests for the Reddit fetch seam and fan-out worker pool.

No network. Fake sessions drive the warm + rotate-on-block + backoff paths
deterministically (in live runs the first IP warms and returns 200s, so these
branches rarely fire). The fake holder fakes the warm's cookie jar.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

import pytest

from proprietary.reddit import fetch, scraper
from proprietary.reddit.fetch import (
    RedditAccessBlockedError,
    _current_session,
    fetch_page,
)

_PAGE = "<shreddit-app></shreddit-app>"


class _FakePage:
    def __init__(self, status: int, *, payload=None):
        self.status = status
        self.body = payload if payload is not None else _PAGE


class _FakeSession:
    """One 'IP': ``can_warm`` gates the warm; page GETs return ``status``."""

    def __init__(
        self,
        status: int = 200,
        *,
        can_warm: bool = True,
        payload=None,
    ) -> None:
        self.status = status
        self.can_warm = can_warm
        self.payload = payload
        self.json_calls = 0

    async def get(self, url, headers=None, cookies=None):
        self.json_calls += 1
        return _FakePage(self.status, payload=self.payload)


class _FakeHolder:
    """Holder whose ``rotate()`` advances to the next fake session (a new IP).

    ``warm()`` fakes the warm: it succeeds (stashing a jar) only when the
    current fake session's ``can_warm`` is set, mirroring a clean vs dirty exit.
    """

    def __init__(self, sessions: list[_FakeSession]) -> None:
        self._sessions = sessions
        self.session = sessions[0]
        self.rotations = 0
        self.warmed = False
        self.proxy = "http://sticky.example:823"
        self.cookies: dict[str, str] = {}
        self.warm_calls = 0

    async def warm(self) -> bool:
        self.warm_calls += 1
        if self.session.can_warm:
            self.cookies = {"loid": "x"}
            return True
        return False

    async def rotate(self):
        self.rotations += 1
        self.session = self._sessions[min(self.rotations, len(self._sessions) - 1)]
        self.warmed = False  # loid binds to the IP: re-warm on the fresh one
        self.cookies = {}
        return self.session

    async def pace(self) -> None:
        return None

    async def close(self) -> None:
        return None


def _no_sleep(monkeypatch) -> None:
    async def _noop(_seconds):
        return None

    monkeypatch.setattr(fetch.asyncio, "sleep", _noop)


async def test_warms_then_returns_the_page():
    # The first IP warms (mints a jar) -> a single warm call, no rotation.
    holder = _FakeHolder([_FakeSession(200, can_warm=True)])
    token = _current_session.set(holder)
    try:
        result = await fetch_page("r/python/hot")
    finally:
        _current_session.reset(token)
    assert result == _PAGE
    assert holder.rotations == 0
    assert holder.warm_calls == 1  # warmed exactly once
    assert holder.cookies == {"loid": "x"}  # jar stashed for the page fetch


async def test_rotates_when_warm_fails_then_succeeds():
    # IP0 can't mint loid at all -> rotate; IP1 warms fine.
    holder = _FakeHolder(
        [
            _FakeSession(200, can_warm=False),
            _FakeSession(200, can_warm=True),
        ]
    )
    token = _current_session.set(holder)
    try:
        result = await fetch_page("r/python/hot")
    finally:
        _current_session.reset(token)
    assert result == _PAGE
    assert holder.rotations == 1


async def test_raises_when_no_ip_can_warm():
    holder = _FakeHolder(
        [_FakeSession(200, can_warm=False) for _ in range(fetch._MAX_ROTATIONS + 1)]
    )
    token = _current_session.set(holder)
    try:
        raised = False
        try:
            await fetch_page("r/python/hot")
        except RedditAccessBlockedError:
            raised = True
    finally:
        _current_session.reset(token)
    assert raised
    assert holder.rotations == fetch._MAX_ROTATIONS


async def test_rotates_and_rewarms_on_403():
    holder = _FakeHolder([_FakeSession(403), _FakeSession(200, can_warm=True)])
    token = _current_session.set(holder)
    try:
        result = await fetch_page("r/python/hot")
    finally:
        _current_session.reset(token)
    assert result == _PAGE
    assert holder.rotations == 1
    assert holder.warm_calls == 2  # re-warmed on the fresh IP after the 403


async def test_a_challenge_page_rotates_to_a_fresh_exit_rather_than_being_solved():
    """Reddit's JavaScript check on a full page; the next exit is served it plainly."""
    check = '<script>e.elements.namedItem("solution").value=n</script>'
    holder = _FakeHolder(
        [_FakeSession(200, payload=check), _FakeSession(200, can_warm=True)]
    )
    token = _current_session.set(holder)
    try:
        result = await fetch_page("comments/abc")
    finally:
        _current_session.reset(token)
    assert result == _PAGE
    assert holder.rotations == 1


async def test_a_404_is_asked_once_more_on_a_fresh_exit():
    """An existing post's page answered 404 once in about 30 (2026-10-23), and the
    call returned no items. A missing post is a 200 page with no post in it."""
    holder = _FakeHolder([_FakeSession(404), _FakeSession(200)])
    token = _current_session.set(holder)
    try:
        result = await fetch_page("comments/1xbnrhi/")
    finally:
        _current_session.reset(token)
    assert result == _PAGE
    assert holder.rotations == 1


async def test_a_404_on_two_exits_returns_none():
    holder = _FakeHolder([_FakeSession(404), _FakeSession(404), _FakeSession(200)])
    token = _current_session.set(holder)
    try:
        result = await fetch_page("comments/gone/")
    finally:
        _current_session.reset(token)
    assert result is None
    assert holder.rotations == 1


async def test_429_backs_off_without_rotating(monkeypatch):
    _no_sleep(monkeypatch)
    # Same IP: 429 first, then a healthy 200 on retry (no rotation).
    session = _FakeSession(429)

    async def _get(url, headers=None, cookies=None):
        session.json_calls += 1
        return _FakePage(429 if session.json_calls == 1 else 200)

    session.get = _get  # type: ignore[method-assign]
    holder = _FakeHolder([session])
    token = _current_session.set(holder)
    try:
        result = await fetch_page("r/python/hot")
    finally:
        _current_session.reset(token)
    assert result == _PAGE
    assert holder.rotations == 0


async def test_persistent_403_raises_blocked(monkeypatch):
    _no_sleep(monkeypatch)
    holder = _FakeHolder([_FakeSession(403) for _ in range(fetch._MAX_ROTATIONS + 1)])
    token = _current_session.set(holder)
    try:
        raised = False
        try:
            await fetch_page("r/python/hot")
        except RedditAccessBlockedError:
            raised = True
    finally:
        _current_session.reset(token)
    assert raised
    assert holder.rotations == fetch._MAX_ROTATIONS


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
        if len(collected) >= 3:
            break
    await gen.aclose()

    assert len(collected) >= 3
    assert holders, "workers should have opened sessions"
    assert all(h.closed for h in holders), "a worker leaked its proxy session"


async def test_fan_out_empty_jobs_is_noop():
    out = [x async for x in scraper.fan_out([])]
    assert out == []


async def test_a_refused_post_leaves_its_subreddit_and_id_out_of_the_log(
    monkeypatch, caplog
):
    _no_sleep(monkeypatch)
    holder = _FakeHolder([_FakeSession(403) for _ in range(fetch._MAX_ROTATIONS + 1)])

    async def _open():
        return holder

    monkeypatch.setattr(scraper, "open_proxy_holder", _open)

    async def _post() -> AsyncIterator[dict]:
        yield await fetch_page("r/privatesub/comments/abc123")

    caplog.set_level(logging.DEBUG)
    with pytest.raises(RedditAccessBlockedError) as refused:
        async for _ in scraper.fan_out([_post()], concurrency=1):
            pass

    # The user still hears which post was refused; the log does not.
    assert "r/privatesub/comments/abc123" in str(refused.value)
    assert "fan-out job failed: RedditAccessBlockedError" in caplog.text
    assert "privatesub" not in caplog.text
    assert "abc123" not in caplog.text


# Cross-country rotation lives in proprietary.scraping.proxy.rotation and is shared with the
# TikTok sibling; its unit tests live in tests/unit/utils/proxy/test_rotation.py.


def test_rotation_budget_tries_every_country():
    """A wholly blocked lead pool must not fail a job before every pool is tried."""
    from proprietary.scraping.proxy import rotation

    assert len(rotation.FALLBACK_COUNTRIES) <= fetch._MAX_ROTATIONS
