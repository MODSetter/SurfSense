"""Offline tests for the rotate-on-block fetch loop (no network, fake session)."""

from __future__ import annotations

import pytest

from app.proprietary.platforms.indeed_jobs.fetch import (
    IndeedAccessBlockedError,
    IndeedSession,
)

_OK_HTML = "<html>jobs listing</html>"
_BLOCK_HTML = "<html>secure.indeed.com security check</html>"


class _FakePage:
    def __init__(self, html: str, url: str) -> None:
        self.html_content = html
        self.url = url


class _Controller:
    """Shared state across sessions the factory hands out (survives rotation)."""

    def __init__(self, target_outcomes: list[str]) -> None:
        self.target_outcomes = target_outcomes
        self.sessions_started = 0
        self.home_fetches: dict[str, int] = {}
        self.target_index = 0

    def factory(self) -> _FakeSession:
        return _FakeSession(self)


class _FakeSession:
    def __init__(self, ctrl: _Controller) -> None:
        self._ctrl = ctrl

    async def start(self) -> None:
        self._ctrl.sessions_started += 1

    async def close(self) -> None:
        pass

    async def fetch(self, url: str, **_: object) -> _FakePage:
        if url.endswith("/") and "/jobs" not in url:  # warm-up hit
            self._ctrl.home_fetches[url] = self._ctrl.home_fetches.get(url, 0) + 1
            return _FakePage("<html>home</html>", url)
        outcome = self._ctrl.target_outcomes[self._ctrl.target_index]
        self._ctrl.target_index += 1
        if outcome == "OK":
            return _FakePage(_OK_HTML, url)
        if outcome == "ERROR":
            raise RuntimeError("boom")
        return _FakePage(_BLOCK_HTML, "https://secure.indeed.com/auth")


_URL = "https://www.indeed.com/jobs?q=dev"


@pytest.mark.asyncio
async def test_rotates_past_a_block_then_succeeds():
    ctrl = _Controller(["BLOCK", "OK"])
    session = IndeedSession(ctrl.factory)
    html = await session.fetch_html(_URL)
    assert html == _OK_HTML
    assert session.rotations == 1
    assert ctrl.sessions_started == 2  # initial + one rotation


@pytest.mark.asyncio
async def test_recovers_after_a_fetch_error():
    ctrl = _Controller(["ERROR", "OK"])
    session = IndeedSession(ctrl.factory)
    assert await session.fetch_html(_URL) == _OK_HTML
    assert session.rotations == 1


@pytest.mark.asyncio
async def test_raises_after_exhausting_rotations():
    ctrl = _Controller(["BLOCK"] * 10)
    session = IndeedSession(ctrl.factory)
    with pytest.raises(IndeedAccessBlockedError):
        await session.fetch_html(_URL)
    assert session.rotations == 3


@pytest.mark.asyncio
async def test_max_rotations_zero_fails_fast():
    # A gated page (pagination) must raise on the first block without rotating.
    ctrl = _Controller(["BLOCK", "OK"])
    session = IndeedSession(ctrl.factory)
    with pytest.raises(IndeedAccessBlockedError):
        await session.fetch_html(_URL, max_rotations=0)
    assert session.rotations == 0


@pytest.mark.asyncio
async def test_warms_domain_once_without_rotation():
    ctrl = _Controller(["OK", "OK"])
    session = IndeedSession(ctrl.factory)
    await session.fetch_html(_URL)
    await session.fetch_html(_URL + "&start=10")
    assert ctrl.home_fetches["https://www.indeed.com/"] == 1
    await session.close()
