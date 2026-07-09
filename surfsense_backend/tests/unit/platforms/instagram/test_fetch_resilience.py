"""Offline resilience tests for the Instagram fetch seam and fan-out worker pool.

No network. Fake sessions drive the ``csrftoken`` warm-up + rotate-on-block +
backoff paths deterministically (in live runs the first IP warms and returns
200s, so these branches rarely fire). Mirrors the reddit sibling's
``test_fetch_resilience.py`` shape, adapted to Instagram's cookie warm-up.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.proprietary.platforms.instagram import fetch, scraper
from app.proprietary.platforms.instagram.fetch import (
    InstagramAccessBlockedError,
    _current_session,
    fetch_json,
)

_PAYLOAD = {"data": {"user": {"username": "natgeo"}}}


class _FakePage:
    def __init__(
        self, status: int, *, cookies: dict | None = None, payload=None, url=None
    ):
        self.status = status
        self.cookies = cookies or {}
        self.url = url
        self._payload = payload if payload is not None else _PAYLOAD

    def json(self):
        return self._payload

    @property
    def body(self) -> str:
        return json.dumps(self._payload)


class _FakeSession:
    """One 'IP': the warm-up GET mints csrftoken per flag; endpoint GETs return ``status``."""

    def __init__(
        self,
        status: int = 200,
        *,
        csrftoken: bool = True,
        payload=None,
        login_wall: bool = False,
    ) -> None:
        self.status = status
        self.csrftoken = csrftoken
        self.payload = payload
        self.login_wall = login_wall
        self.json_calls = 0
        self.warm_calls = 0

    async def get(self, url, headers=None, cookies=None):
        if url.rstrip("/") == "https://www.instagram.com":
            self.warm_calls += 1
            ck = {"csrftoken": "x", "mid": "y"} if self.csrftoken else {}
            return _FakePage(200, cookies=ck)
        self.json_calls += 1
        # A soft login wall: 200, but the final URL is the login page.
        final = "https://www.instagram.com/accounts/login/" if self.login_wall else url
        return _FakePage(self.status, payload=self.payload, url=final)


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
        self.warmed = False  # cookies bind to the IP: re-warm on the fresh one
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
    holder = _FakeHolder([_FakeSession(200, csrftoken=True)])
    token = _current_session.set(holder)
    try:
        result = await fetch_json("api/v1/users/web_profile_info/", {"username": "natgeo"})
    finally:
        _current_session.reset(token)
    assert result == _PAYLOAD
    assert holder.rotations == 0
    assert holder.session.warm_calls == 1  # warmed exactly once


async def test_rotates_when_warm_fails_then_succeeds():
    holder = _FakeHolder(
        [_FakeSession(200, csrftoken=False), _FakeSession(200, csrftoken=True)]
    )
    token = _current_session.set(holder)
    try:
        result = await fetch_json("api/v1/users/web_profile_info/")
    finally:
        _current_session.reset(token)
    assert result == _PAYLOAD
    assert holder.rotations == 1


async def test_raises_when_no_ip_can_warm():
    holder = _FakeHolder(
        [_FakeSession(200, csrftoken=False) for _ in range(fetch._MAX_ROTATIONS + 1)]
    )
    token = _current_session.set(holder)
    try:
        raised = False
        try:
            await fetch_json("api/v1/users/web_profile_info/")
        except InstagramAccessBlockedError:
            raised = True
    finally:
        _current_session.reset(token)
    assert raised
    assert holder.rotations == fetch._MAX_ROTATIONS


async def test_rotates_and_rewarms_on_403():
    holder = _FakeHolder([_FakeSession(403), _FakeSession(200)])
    token = _current_session.set(holder)
    try:
        result = await fetch_json("api/v1/users/web_profile_info/")
    finally:
        _current_session.reset(token)
    assert result == _PAYLOAD
    assert holder.rotations == 1
    assert holder.session.warm_calls == 1  # re-warmed on the fresh IP


async def test_rotates_on_401_login_wall():
    holder = _FakeHolder([_FakeSession(401), _FakeSession(200)])
    token = _current_session.set(holder)
    try:
        result = await fetch_json("api/v1/users/web_profile_info/")
    finally:
        _current_session.reset(token)
    assert result == _PAYLOAD
    assert holder.rotations == 1


async def test_rotates_on_login_redirect_then_succeeds():
    # 200 status but redirected to /accounts/login/: a soft block that must
    # rotate to a fresh IP, not be mistaken for an empty result.
    holder = _FakeHolder(
        [_FakeSession(200, login_wall=True), _FakeSession(200)]
    )
    token = _current_session.set(holder)
    try:
        result = await fetch_json("api/v1/tags/web_info/", {"tag_name": "travel"})
    finally:
        _current_session.reset(token)
    assert result == _PAYLOAD
    assert holder.rotations == 1


async def test_persistent_login_redirect_raises_blocked():
    holder = _FakeHolder(
        [
            _FakeSession(200, login_wall=True)
            for _ in range(fetch._MAX_ROTATIONS + 1)
        ]
    )
    token = _current_session.set(holder)
    try:
        raised = False
        try:
            await fetch_json("api/v1/tags/web_info/", {"tag_name": "travel"})
        except InstagramAccessBlockedError:
            raised = True
    finally:
        _current_session.reset(token)
    assert raised
    assert holder.rotations == fetch._MAX_ROTATIONS


async def test_404_returns_none_without_rotating():
    holder = _FakeHolder([_FakeSession(404), _FakeSession(200)])
    token = _current_session.set(holder)
    try:
        result = await fetch_json("api/v1/tags/web_info/")
    finally:
        _current_session.reset(token)
    assert result is None
    assert holder.rotations == 0


async def test_429_backs_off_without_rotating(monkeypatch):
    _no_sleep(monkeypatch)
    session = _FakeSession(429)

    async def _get(url, headers=None, cookies=None):
        if url.rstrip("/") == "https://www.instagram.com":
            session.warm_calls += 1
            return _FakePage(200, cookies={"csrftoken": "x"})
        session.json_calls += 1
        return _FakePage(429 if session.json_calls == 1 else 200)

    session.get = _get  # type: ignore[method-assign]
    holder = _FakeHolder([session])
    token = _current_session.set(holder)
    try:
        result = await fetch_json("api/v1/users/web_profile_info/")
    finally:
        _current_session.reset(token)
    assert result == _PAYLOAD
    assert holder.rotations == 0


async def test_persistent_403_raises_blocked(monkeypatch):
    _no_sleep(monkeypatch)
    holder = _FakeHolder([_FakeSession(403) for _ in range(fetch._MAX_ROTATIONS + 1)])
    token = _current_session.set(holder)
    try:
        raised = False
        try:
            await fetch_json("api/v1/users/web_profile_info/")
        except InstagramAccessBlockedError:
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


async def test_fan_out_propagates_blocked_without_deadlock(monkeypatch):
    # Regression: a worker that raises InstagramAccessBlockedError used to strand
    # the exception on its task and deadlock the consumer on results.get(). It
    # must surface as InstagramAccessBlockedError, not hang.
    async def _fake_open():
        return _TrackingHolder()

    @asynccontextmanager
    async def _fake_bind(_holder):
        yield _holder

    monkeypatch.setattr(scraper, "open_proxy_holder", _fake_open)
    monkeypatch.setattr(scraper, "bind_proxy_holder", _fake_bind)

    async def _blocked_job() -> AsyncIterator[dict]:
        raise InstagramAccessBlockedError("login wall")
        yield {}  # unreachable; makes this an async generator

    raised = False
    try:
        async with asyncio.timeout(5):  # fail fast if the deadlock regresses
            async for _ in scraper.fan_out([_blocked_job()], concurrency=1):
                pass
    except InstagramAccessBlockedError:
        raised = True
    assert raised, "hard block must propagate, not deadlock"


def _profile_payload(username: str, n: int) -> dict:
    # IDs namespaced per target so cross-target de-dup doesn't collapse them.
    return {
        "data": {
            "user": {
                "id": f"u_{username}",
                "username": username,
                "edge_owner_to_timeline_media": {
                    "count": n,
                    "edges": [{"node": {"id": f"{username}:{i}"}} for i in range(n)],
                },
            }
        }
    }


async def test_scrape_instagram_closes_sessions_when_limit_stops_inflight_workers(
    monkeypatch,
):
    """Hitting ``limit`` must tear down the whole fan-out chain deterministically.

    Regression: closing the outer ``iter_instagram`` generator does NOT
    synchronously close the inner ``fan_out`` it loops over — CPython defers that
    to async-gen GC — so without an explicit ``aclosing`` the collector's early
    ``break`` leaked every warm proxy session that was still mid-fetch. The
    ``fan_out``-direct test misses this because instant jobs self-drain before
    cancellation ever runs; here each fetch yields to the loop so workers are
    genuinely in-flight when the limit trips.
    """
    holders: list[_TrackingHolder] = []

    async def _fake_open():
        h = _TrackingHolder()
        holders.append(h)
        return h

    @asynccontextmanager
    async def _fake_bind(_holder):
        yield _holder

    async def _fetch(path, params=None):
        await asyncio.sleep(0)  # yield control: keep sibling workers in-flight
        username = (params or {}).get("username", "acct")
        return _profile_payload(username, 5)

    monkeypatch.setattr(scraper, "open_proxy_holder", _fake_open)
    monkeypatch.setattr(scraper, "bind_proxy_holder", _fake_bind)
    monkeypatch.setattr(scraper, "fetch_json", _fetch)

    model = scraper.InstagramScrapeInput(
        resultsType="posts",
        directUrls=[f"https://www.instagram.com/acct{i}/" for i in range(50)],
        resultsLimit=5,
    )
    items = await scraper.scrape_instagram(model, limit=3)

    assert len(items) == 3
    assert holders, "workers should have opened sessions"
    assert all(h.closed for h in holders), "early stop leaked a proxy session"
