"""Fetch-seam resilience for the TikTok scraper (no network, fake holders).

A fake holder stands in for the shared keep-alive session: each of its 'IPs'
drives the cookie warm-up, rotate-on-block and backoff branches
deterministically. A live first IP normally returns 200s.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from proprietary.scraping import http, sessions
from proprietary.tiktok.session import TikTokAccessBlockedError, client, proxy

_BLOB = '<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__">{}</script>'
_HTML = f"<html><body>{_BLOB}</body></html>"


class _FakeResponse:
    def __init__(self, status: int, body: str = "", cookies: dict | None = None):
        self.status = status
        self.body = body.encode()
        self.cookies = cookies or {}

    def text(self) -> str:
        return self.body.decode()

    def json(self) -> Any:
        return json.loads(self.body)


class _FakeIP:
    """One exit: homepage warm mints ``ttwid`` per flag; other GETs return ``status``."""

    def __init__(
        self, status: int = 200, *, warms: bool = True, body: str = _HTML
    ) -> None:
        self.status = status
        self.warms = warms
        self.body = body
        self.page_calls = 0
        self.warm_calls = 0
        self.referers: list[str | None] = []


class _FakeHolder:
    """The parts of ``sessions.SessionHolder`` the fetch loop uses."""

    def __init__(self, ips: list[_FakeIP | Exception]) -> None:
        self._ips = ips
        self.rotations = 0
        self.countries: list[str | None] = []
        self.exit = sessions.Exit("us")

    @property
    def ip(self) -> Any:
        return self._ips[min(self.rotations, len(self._ips) - 1)]

    async def rotate(self, reason: str, *, country=None, seen=None) -> None:
        if seen is not None and seen != self.rotations:
            return
        self.rotations += 1
        self.countries.append(country)

    async def request(self, method: str, url: str, *, stage: str, **kw: Any):
        ip = self.ip
        if isinstance(ip, Exception):
            raise ip
        if url.rstrip("/") == "https://www.tiktok.com":
            ip.warm_calls += 1
            return _FakeResponse(200, "<html/>", {"ttwid": "x"} if ip.warms else {})
        ip.page_calls += 1
        ip.referers.append((kw.get("headers") or {}).get("Referer"))
        return _FakeResponse(ip.status, ip.body if ip.status == 200 else "")


def _quiet(monkeypatch) -> None:
    async def _noop(_seconds):
        return None

    monkeypatch.setattr(client.asyncio, "sleep", _noop)
    monkeypatch.setattr(proxy, "_MIN_INTERVAL_S", 0)


async def _fetch_html(holder: _FakeHolder, url: str) -> str | None:
    with sessions.bind(holder):
        return await client.fetch_html(url)


async def test_a_page_is_fetched_cold_without_a_warm_up(monkeypatch):
    _quiet(monkeypatch)
    holder = _FakeHolder([_FakeIP(200)])

    result = await _fetch_html(holder, "https://www.tiktok.com/@scout/video/1")

    assert result == _HTML
    assert holder.rotations == 0
    assert holder.ip.warm_calls == 0  # TT-6: the cold page carries its blob


async def test_a_page_without_its_blob_is_retried_once_warmed(monkeypatch):
    _quiet(monkeypatch)
    holder = _FakeHolder([_FakeIP(200, body="<html>no blob</html>")])

    result = await _fetch_html(holder, "https://www.tiktok.com/@scout/video/1")

    assert result == "<html>no blob</html>"
    assert holder.ip.warm_calls == 1
    assert holder.ip.page_calls == 2


async def test_the_page_warm_up_kill_switch_warms_first(monkeypatch):
    _quiet(monkeypatch)
    monkeypatch.setattr(client, "_PAGE_WARMUP", True)
    holder = _FakeHolder([_FakeIP(200, warms=False), _FakeIP(200, warms=True)])

    result = await _fetch_html(holder, "https://www.tiktok.com/@scout2015")

    assert result == _HTML
    assert holder.rotations == 1  # the first IP never minted ttwid


async def test_404_returns_none_without_rotating(monkeypatch):
    _quiet(monkeypatch)
    holder = _FakeHolder([_FakeIP(404), _FakeIP(200)])

    assert await _fetch_html(holder, "https://www.tiktok.com/@missing") is None
    assert holder.rotations == 0


async def test_rotates_to_the_next_country_on_403(monkeypatch):
    _quiet(monkeypatch)
    monkeypatch.setattr(
        proxy, "country_for_rotation", lambda n: ("us", "gb", "de")[n % 3]
    )
    holder = _FakeHolder([_FakeIP(403), _FakeIP(200)])

    result = await _fetch_html(holder, "https://www.tiktok.com/@scout2015")

    assert result == _HTML
    assert holder.rotations == 1
    assert holder.countries == ["gb"]


async def test_a_dead_exit_rotates_like_a_block(monkeypatch):
    _quiet(monkeypatch)
    dead = http.TransportError("Timeout", 28, 5000.0, "timed out")
    holder = _FakeHolder([dead, _FakeIP(200)])

    assert await _fetch_html(holder, "https://www.tiktok.com/@a/video/1") == _HTML
    assert holder.rotations == 1


async def test_persistent_403_raises_blocked(monkeypatch):
    _quiet(monkeypatch)
    holder = _FakeHolder([_FakeIP(403) for _ in range(client._MAX_ROTATIONS + 1)])

    raised = False
    try:
        await _fetch_html(holder, "https://www.tiktok.com/@scout2015")
    except TikTokAccessBlockedError:
        raised = True

    assert raised
    assert holder.rotations == client._MAX_ROTATIONS


async def test_429_backs_off_on_the_same_ip(monkeypatch):
    _quiet(monkeypatch)
    ip = _FakeIP(429)
    holder = _FakeHolder([ip])
    calls = 0
    real = holder.request

    async def flaky(method, url, **kw):
        nonlocal calls
        calls += 1
        if calls == 2:
            ip.status = 200
        return await real(method, url, **kw)

    holder.request = flaky

    assert await _fetch_html(holder, "https://www.tiktok.com/@a/video/1") == _HTML
    assert holder.rotations == 0


async def test_without_a_bound_holder_it_opens_one_for_the_call(monkeypatch):
    _quiet(monkeypatch)
    opened: list[_FakeHolder] = []

    class _Bound:
        async def __aenter__(self):
            holder = _FakeHolder([_FakeIP(200)])
            opened.append(holder)
            self._cm = sessions.bind(holder)
            self._cm.__enter__()
            return holder

        async def __aexit__(self, *exc):
            self._cm.__exit__(*exc)

    monkeypatch.setattr(client, "proxy_session", _Bound)

    assert await client.fetch_html("https://www.tiktok.com/@a/video/1") == _HTML
    assert len(opened) == 1
    assert sessions.current() is None


async def test_a_slow_page_is_hedged_on_a_fresh_exit(monkeypatch):
    _quiet(monkeypatch)
    monkeypatch.setattr(client, "_PAGE_HEDGE_S", 0.05)
    slow = _FakeHolder([_FakeIP(200, body="<html>slow</html>")])
    real = slow.request
    cancelled: list[bool] = []

    async def stalled(method, url, **kw):
        try:
            # A dead exit, short of its connect cap (asyncio.sleep is stubbed here).
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.append(True)
            raise
        return await real(method, url, **kw)

    slow.request = stalled
    fresh: list[_FakeHolder] = []

    class _Fresh:
        async def __aenter__(self):
            holder = _FakeHolder([_FakeIP(200)])
            fresh.append(holder)
            self._cm = sessions.bind(holder)
            self._cm.__enter__()
            return holder

        async def __aexit__(self, *exc):
            self._cm.__exit__(*exc)

    monkeypatch.setattr(client, "proxy_session", _Fresh)

    result = await asyncio.wait_for(
        _fetch_html(slow, "https://www.tiktok.com/@a/video/1"), timeout=2
    )

    assert result == _HTML  # the hedge's page
    assert len(fresh) == 1
    assert cancelled == [True]


async def test_the_page_hedge_has_a_kill_switch(monkeypatch):
    _quiet(monkeypatch)
    monkeypatch.setattr(client, "_PAGE_HEDGE_S", 0)

    async def no_hedge(*_a, **_kw):
        raise AssertionError("hedged must not run")

    monkeypatch.setattr(client, "hedged", no_hedge)
    holder = _FakeHolder([_FakeIP(200)])

    assert await _fetch_html(holder, "https://www.tiktok.com/@a/video/1") == _HTML


async def test_each_rotation_is_reported_as_a_stage(monkeypatch):
    _quiet(monkeypatch)
    dead = http.TransportError("Timeout", 28, 5000.0, "timed out")
    holder = _FakeHolder([dead, _FakeIP(200)])
    heard: list[str] = []

    async def hear(message: str) -> None:
        heard.append(message)

    monkeypatch.setattr(client, "_PAGE_HEDGE_S", 0)
    token = proxy.on_stage.set(hear)
    try:
        await _fetch_html(holder, "https://www.tiktok.com/@a/video/1")
    finally:
        proxy.on_stage.reset(token)

    assert heard == ["page: new exit (Timeout)"]


async def test_fetch_json_tells_a_failed_get_from_a_withheld_body(monkeypatch):
    _quiet(monkeypatch)
    holder = _FakeHolder([_FakeIP(500)])

    with sessions.bind(holder):
        got = await client.fetch_json("https://www.tiktok.com/api/x", warm=False)

    assert got is client._UNREACHABLE
