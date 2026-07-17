"""Offline resilience tests for the Reddit fetch seam and fan-out worker pool.

No network. Fake sessions drive the ``loid`` warm-up + rotate-on-block + backoff
paths deterministically (in live runs the first IP warms and returns 200s, so
these branches rarely fire). Mirrors the youtube sibling's
``test_fetch_resilience.py`` shape, extended with a fake warm-up.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from app.proprietary.platforms.reddit import fetch, scraper
from app.proprietary.platforms.reddit.fetch import (
    RedditAccessBlockedError,
    _current_session,
    fetch_json,
)

_LISTING = {"kind": "Listing", "data": {"children": [], "after": None}}


class _FakePage:
    def __init__(self, status: int, *, cookies: dict | None = None, payload=None):
        self.status = status
        self.cookies = cookies or {}
        self._payload = payload if payload is not None else _LISTING

    def json(self):
        return self._payload

    @property
    def body(self) -> str:
        return json.dumps(self._payload)


class _FakeSession:
    """One 'IP': warm-up mints loid per flags; ``.json`` GETs return ``status``."""

    def __init__(
        self,
        status: int = 200,
        *,
        shreddit_loid: bool = True,
        old_loid: bool = False,
        payload=None,
    ) -> None:
        self.status = status
        self.shreddit_loid = shreddit_loid
        self.old_loid = old_loid
        self.payload = payload
        self.json_calls = 0
        self.warm_calls = 0

    async def get(self, url, headers=None, cookies=None):
        if "svc/shreddit" in url:
            self.warm_calls += 1
            ck = {"loid": "x", "session_tracker": "y"} if self.shreddit_loid else {}
            return _FakePage(200, cookies=ck)
        if "old.reddit.com" in url:
            self.warm_calls += 1
            return _FakePage(200, cookies={"loid": "x"} if self.old_loid else {})
        self.json_calls += 1
        return _FakePage(self.status, payload=self.payload)


class _FakeHolder:
    """Holder whose ``rotate()`` advances to the next fake session (a new IP)."""

    def __init__(self, sessions: list[_FakeSession]) -> None:
        self._sessions = sessions
        self.session = sessions[0]
        self.rotations = 0
        self.warmed = False

    async def rotate(self):
        self.rotations += 1
        self.session = self._sessions[min(self.rotations, len(self._sessions) - 1)]
        self.warmed = False  # loid binds to the IP: re-warm on the fresh one
        return self.session

    async def pace(self) -> None:
        return None

    async def close(self) -> None:
        return None


def _no_sleep(monkeypatch) -> None:
    async def _noop(_seconds):
        return None

    monkeypatch.setattr(fetch.asyncio, "sleep", _noop)


async def test_warms_then_returns_json():
    # shreddit is tried first and mints loid -> a single warm call.
    holder = _FakeHolder([_FakeSession(200, shreddit_loid=True)])
    token = _current_session.set(holder)
    try:
        result = await fetch_json("r/python/hot")
    finally:
        _current_session.reset(token)
    assert result == _LISTING
    assert holder.rotations == 0
    assert holder.session.warm_calls == 1  # warmed exactly once


async def test_warm_falls_back_to_old_reddit():
    # shreddit doesn't mint loid, old.reddit does -> still warms on the same IP.
    holder = _FakeHolder([_FakeSession(200, shreddit_loid=False, old_loid=True)])
    token = _current_session.set(holder)
    try:
        result = await fetch_json("r/python/hot")
    finally:
        _current_session.reset(token)
    assert result == _LISTING
    assert holder.rotations == 0


async def test_rotates_when_warm_fails_then_succeeds():
    # IP0 can't mint loid at all -> rotate; IP1 warms fine.
    holder = _FakeHolder(
        [
            _FakeSession(200, shreddit_loid=False, old_loid=False),
            _FakeSession(200, shreddit_loid=True),
        ]
    )
    token = _current_session.set(holder)
    try:
        result = await fetch_json("r/python/hot")
    finally:
        _current_session.reset(token)
    assert result == _LISTING
    assert holder.rotations == 1


async def test_raises_when_no_ip_can_warm():
    holder = _FakeHolder(
        [
            _FakeSession(200, shreddit_loid=False, old_loid=False)
            for _ in range(fetch._MAX_ROTATIONS + 1)
        ]
    )
    token = _current_session.set(holder)
    try:
        raised = False
        try:
            await fetch_json("r/python/hot")
        except RedditAccessBlockedError:
            raised = True
    finally:
        _current_session.reset(token)
    assert raised
    assert holder.rotations == fetch._MAX_ROTATIONS


async def test_rotates_and_rewarms_on_403():
    holder = _FakeHolder([_FakeSession(403), _FakeSession(200, old_loid=True)])
    token = _current_session.set(holder)
    try:
        result = await fetch_json("r/python/hot")
    finally:
        _current_session.reset(token)
    assert result == _LISTING
    assert holder.rotations == 1
    assert holder.session.warm_calls == 1  # re-warmed on the fresh IP


async def test_404_returns_none_without_rotating():
    holder = _FakeHolder([_FakeSession(404), _FakeSession(200)])
    token = _current_session.set(holder)
    try:
        result = await fetch_json("r/python/comments/missing")
    finally:
        _current_session.reset(token)
    assert result is None
    assert holder.rotations == 0


async def test_429_backs_off_without_rotating(monkeypatch):
    _no_sleep(monkeypatch)
    # Same IP: 429 first, then a healthy 200 on retry (no rotation).
    session = _FakeSession(429)

    async def _get(url, headers=None, cookies=None):
        if "svc/shreddit" in url or "old.reddit.com" in url:
            session.warm_calls += 1
            return _FakePage(200, cookies={"loid": "x"})
        session.json_calls += 1
        return _FakePage(429 if session.json_calls == 1 else 200)

    session.get = _get  # type: ignore[method-assign]
    holder = _FakeHolder([session])
    token = _current_session.set(holder)
    try:
        result = await fetch_json("r/python/hot")
    finally:
        _current_session.reset(token)
    assert result == _LISTING
    assert holder.rotations == 0


async def test_persistent_403_raises_blocked(monkeypatch):
    _no_sleep(monkeypatch)
    holder = _FakeHolder([_FakeSession(403) for _ in range(fetch._MAX_ROTATIONS + 1)])
    token = _current_session.set(holder)
    try:
        raised = False
        try:
            await fetch_json("r/python/hot")
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


# Cross-country rotation lives in app.utils.proxy.rotation and is shared with the
# TikTok sibling; its unit tests live in tests/unit/utils/proxy/test_rotation.py.
