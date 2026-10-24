"""Unit tests for bounded navigation and on-demand challenge solving.

Offline: pages and the scrapling session are fakes that record what was awaited.
The challenge markup is a trimmed Cloudflare interstitial of the shape scrapling
detects (no tokens), and a clean page that only mentions Cloudflare in prose.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from patchright.async_api import Error as PatchrightError
from patchright.async_api import TimeoutError as PatchrightTimeoutError

from proprietary.scraping import settle
from proprietary.scraping.browser_pool import PooledPage

FIXTURES = Path(__file__).parent / "fixtures"


class FakeResponse:
    def __init__(self, status: int = 200, headers: dict | None = None) -> None:
        self.status = status
        self.headers = headers or {"content-type": "text/html"}


class FakePage:
    def __init__(self, *, response=None, attaches=True, idles=True, html=""):
        self.response = response if response is not None else FakeResponse()
        self.attaches = attaches
        self.idles = idles
        self.html = html
        self.calls: list[tuple] = []
        self.closed = False

    async def goto(self, url, *, wait_until, timeout, referer):  # noqa: ASYNC109
        self.calls.append(("goto", url, wait_until, timeout, referer))
        return self.response

    async def wait_for_load_state(self, state, timeout=None):  # noqa: ASYNC109
        self.calls.append(("state", state, timeout))
        if state == "networkidle" and not self.idles:
            raise PatchrightTimeoutError("never idle")

    async def wait_for_selector(self, selector, *, state, timeout):  # noqa: ASYNC109
        self.calls.append(("selector", selector, state, timeout))
        if not self.attaches:
            raise PatchrightTimeoutError("not attached")

    async def content(self) -> str:
        return self.html

    def is_closed(self) -> bool:
        return self.closed


@pytest.mark.asyncio
async def test_goto_commits_then_waits_only_for_the_named_state():
    page = FakePage()
    landing = await settle.goto(
        page, "https://www.indeed.com/jobs?q=x", referer="https://www.google.com/"
    )
    assert page.calls == [
        (
            "goto",
            "https://www.indeed.com/jobs?q=x",
            "commit",
            10000,
            "https://www.google.com/",
        ),
        ("state", "domcontentloaded", None),
    ]
    assert landing.status == 200 and landing.ready
    assert landing.headers == {"content-type": "text/html"}
    assert set(landing.ms) == {"commit", "domcontentloaded"}


@pytest.mark.asyncio
async def test_goto_commit_only_with_a_ready_selector():
    page = FakePage()
    landing = await settle.goto(
        page,
        "https://www.google.com/search?q=x",
        wait_until="commit",
        ready_selector="div.tF2Cxc, div.Gx5Zad",
        ready_timeout_ms=10000,
    )
    assert [c[0] for c in page.calls] == ["goto", "selector"]
    assert page.calls[1] == ("selector", "div.tF2Cxc, div.Gx5Zad", "attached", 10000)
    assert landing.ready and set(landing.ms) == {"commit", "ready"}


@pytest.mark.asyncio
async def test_a_missing_ready_selector_is_reported_not_raised():
    page = FakePage(attaches=False)
    landing = await settle.goto(page, "https://x.test/", ready_selector="#results")
    assert landing.ready is False


@pytest.mark.asyncio
async def test_idle_wait_is_capped_and_never_raises():
    page = FakePage(idles=False)
    landing = await settle.goto(page, "https://x.test/", idle_cap_ms=3000)
    assert ("state", "networkidle", 3000) in page.calls
    assert "idle" in landing.ms


@pytest.mark.asyncio
async def test_navigation_errors_still_raise():
    class Dead(FakePage):
        async def goto(self, url, **kwargs):
            raise PatchrightTimeoutError("no commit")

    with pytest.raises(PatchrightTimeoutError):
        await settle.goto(Dead(), "https://x.test/")


@pytest.mark.asyncio
async def test_a_same_page_navigation_has_no_response():
    page = FakePage()
    page.response = None

    async def goto(url, **kwargs):
        return None

    page.goto = goto
    landing = await settle.goto(page, "https://x.test/#a", wait_until="commit")
    assert landing.response is None and landing.status == 0 and landing.headers == {}


@pytest.mark.asyncio
async def test_wait_state_reports_the_cap():
    assert await settle.wait_state(FakePage(), "load", 8000) is True
    assert await settle.wait_state(FakePage(idles=False), "networkidle", 10) is False


def test_challenge_kind_reads_the_interstitial_markers():
    html = (FIXTURES / "cf_interstitial.html").read_text(encoding="utf-8")
    assert settle.challenge_kind(403, {}, html) == "managed"
    nonint = html.replace("cType: 'managed'", "cType: 'non-interactive'")
    assert settle.challenge_kind(503, {}, nonint) == "non-interactive"


def test_challenge_kind_finds_an_embedded_turnstile():
    html = (
        '<html><body><form><script src="https://challenges.cloudflare.com/turnstile/'
        'v0/api.js" async></script></form></body></html>'
    )
    assert settle.challenge_kind(200, {}, html) == "embedded"


def test_challenge_kind_from_response_only_signals():
    assert settle.challenge_kind(403, {"CF-Mitigated": "challenge"}, "") == "managed"
    page = "<html><head><title>Just a moment...</title></head></html>"
    assert settle.challenge_kind(503, {}, page) == "managed"
    assert settle.challenge_kind(200, {}, page) is None  # a 200 titled so is content


def test_a_clean_page_is_not_a_challenge():
    html = (FIXTURES / "clean_mentions_cloudflare.html").read_text(encoding="utf-8")
    assert settle.challenge_kind(200, {"server": "cloudflare"}, html) is None


class FakeSession:
    def __init__(self, page: FakePage, clears: bool, hang: bool = False) -> None:
        self.page = page
        self.clears = clears
        self.hang = hang
        self.solved = 0

    async def _cloudflare_solver(self, page) -> None:
        assert page is self.page
        self.solved += 1
        if self.hang:
            await asyncio.sleep(3600)
        if self.clears:
            page.html = "<html><body>jobs</body></html>"


def _pooled(page: FakePage, session: FakeSession) -> PooledPage:
    return PooledPage(
        page=page,
        context=None,
        plugin="indeed",
        kept=None,
        queue_ms=0,
        launch_ms=0,
        context_ms=0,
        _session=session,
    )


@pytest.mark.asyncio
async def test_solve_challenge_runs_scraplings_solver_and_checks_it_cleared():
    html = (FIXTURES / "cf_interstitial.html").read_text(encoding="utf-8")
    page = FakePage(html=html)
    session = FakeSession(page, clears=True)
    assert await settle.solve_challenge(_pooled(page, session), "managed") is True
    assert session.solved == 1

    stuck = FakePage(html=html)
    assert (
        await settle.solve_challenge(
            _pooled(stuck, FakeSession(stuck, clears=False)), "managed"
        )
        is False
    )


@pytest.mark.asyncio
async def test_solve_challenge_gives_up_at_its_timeout():
    page = FakePage(html="cType: 'managed'")
    session = FakeSession(page, clears=False, hang=True)
    pooled = _pooled(page, session)
    assert await settle.solve_challenge(pooled, "managed", timeout_s=0.05) is False


class ReloadingPage(FakePage):
    """content() fails while the clearance reload is in flight, as patchright does."""

    def __init__(self, *, fails: int, **kwargs) -> None:
        super().__init__(**kwargs)
        self.fails = fails
        self.reads = 0

    async def content(self) -> str:
        self.reads += 1
        if self.reads <= self.fails:
            raise PatchrightError(
                "Execution context was destroyed, most likely because of a navigation"
            )
        return self.html


@pytest.mark.asyncio
async def test_a_solve_whose_reload_is_still_in_flight_reads_the_cleared_page(
    monkeypatch,
):
    monkeypatch.setattr(settle, "_CONTENT_RETRY_S", 0)
    html = (FIXTURES / "cf_interstitial.html").read_text(encoding="utf-8")
    page = ReloadingPage(fails=2, html=html)
    session = FakeSession(page, clears=True)
    assert await settle.solve_challenge(_pooled(page, session), "managed") is True
    assert page.reads == 3


@pytest.mark.asyncio
async def test_page_content_gives_up_on_a_closed_page_and_after_its_tries(
    monkeypatch,
):
    monkeypatch.setattr(settle, "_CONTENT_RETRY_S", 0)
    closed = ReloadingPage(fails=1)
    closed.closed = True
    with pytest.raises(PatchrightError):
        await settle.page_content(closed)
    assert closed.reads == 1  # no retry on a page that is gone

    stuck = ReloadingPage(fails=100)
    with pytest.raises(PatchrightError):
        await settle.page_content(stuck)
    assert stuck.reads == settle._CONTENT_TRIES


@pytest.mark.asyncio
async def test_a_header_only_challenge_still_titled_just_a_moment_is_not_cleared():
    # cf-mitigated read as 'managed', but the page has no cType for scrapling.
    wall = "<html><head><title>Just a moment...</title></head><body></body></html>"
    page = FakePage(html=wall)
    session = FakeSession(page, clears=False)
    assert settle.challenge_kind(403, {"cf-mitigated": "challenge"}, wall) == "managed"
    assert await settle.solve_challenge(_pooled(page, session), "managed") is False
