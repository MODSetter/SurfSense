"""Fetch-seam resilience for the TikTok scraper (no network, fake sessions).

Fake sessions drive the cookie warm-up + rotate-on-block + backoff branches
deterministically; a live first IP normally warms and returns 200s.
"""

from __future__ import annotations

from app.proprietary.platforms.tiktok.session import (
    TikTokAccessBlockedError,
    client,
)
from app.proprietary.platforms.tiktok.session.proxy import _current_session

_HTML = "<html><body>ok</body></html>"


class _FakePage:
    def __init__(self, status: int, *, cookies: dict | None = None, body: str = _HTML):
        self.status = status
        self.cookies = cookies or {}
        self.body = body

    @property
    def text(self) -> str:
        return self.body


class _FakeSession:
    """One 'IP': homepage warm mints ``ttwid`` per flag; page GETs return ``status``."""

    def __init__(self, status: int = 200, *, warms: bool = True, body: str = _HTML):
        self.status = status
        self.warms = warms
        self.body = body
        self.page_calls = 0
        self.warm_calls = 0

    async def get(self, url, headers=None, cookies=None):
        if url.rstrip("/") == "https://www.tiktok.com":
            self.warm_calls += 1
            return _FakePage(200, cookies={"ttwid": "x"} if self.warms else {})
        self.page_calls += 1
        return _FakePage(self.status, body=self.body)


class _FakeHolder:
    def __init__(self, sessions: list[_FakeSession]) -> None:
        self._sessions = sessions
        self.session = sessions[0]
        self.rotations = 0
        self.warmed = False

    async def rotate(self):
        self.rotations += 1
        self.session = self._sessions[min(self.rotations, len(self._sessions) - 1)]
        self.warmed = False
        return self.session

    async def pace(self) -> None:
        return None

    async def close(self) -> None:
        return None


def _no_sleep(monkeypatch) -> None:
    async def _noop(_seconds):
        return None

    monkeypatch.setattr(client.asyncio, "sleep", _noop)


async def test_warms_then_returns_html():
    holder = _FakeHolder([_FakeSession(200, warms=True)])
    token = _current_session.set(holder)
    try:
        result = await client.fetch_html("https://www.tiktok.com/@scout2015")
    finally:
        _current_session.reset(token)
    assert result == _HTML
    assert holder.rotations == 0
    assert holder.session.warm_calls == 1


async def test_rotates_when_warm_fails_then_succeeds():
    holder = _FakeHolder([_FakeSession(200, warms=False), _FakeSession(200, warms=True)])
    token = _current_session.set(holder)
    try:
        result = await client.fetch_html("https://www.tiktok.com/@scout2015")
    finally:
        _current_session.reset(token)
    assert result == _HTML
    assert holder.rotations == 1


async def test_404_returns_none_without_rotating():
    holder = _FakeHolder([_FakeSession(404), _FakeSession(200)])
    token = _current_session.set(holder)
    try:
        result = await client.fetch_html("https://www.tiktok.com/@missing")
    finally:
        _current_session.reset(token)
    assert result is None
    assert holder.rotations == 0


async def test_rotates_and_rewarms_on_403():
    holder = _FakeHolder([_FakeSession(403), _FakeSession(200, warms=True)])
    token = _current_session.set(holder)
    try:
        result = await client.fetch_html("https://www.tiktok.com/@scout2015")
    finally:
        _current_session.reset(token)
    assert result == _HTML
    assert holder.rotations == 1
    assert holder.session.warm_calls == 1


async def test_persistent_403_raises_blocked(monkeypatch):
    _no_sleep(monkeypatch)
    holder = _FakeHolder(
        [_FakeSession(403) for _ in range(client._MAX_ROTATIONS + 1)]
    )
    token = _current_session.set(holder)
    try:
        raised = False
        try:
            await client.fetch_html("https://www.tiktok.com/@scout2015")
        except TikTokAccessBlockedError:
            raised = True
    finally:
        _current_session.reset(token)
    assert raised
    assert holder.rotations == client._MAX_ROTATIONS
