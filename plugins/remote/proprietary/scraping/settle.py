"""Bounded navigation and on-demand Cloudflare solving for browser-pool pages.

Scrapling's fetch waits for 'load' and then network idle (swallowing its timeout),
and its solver adds up to 5 s even on clean pages, while the data is ready much
earlier: Google's organic results attach at 2.3 s against load at 6.4 s, Indeed's
DOMContentLoaded comes at 1-2 s against 10-35 s for load plus idle. `goto()` waits
only for what the caller names, and the solver runs only when `challenge_kind()`
finds a challenge on the page.

Run these on the browser loop, inside `browser_pool.run(...)`.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from patchright.async_api import Error as PatchrightError
from patchright.async_api import TimeoutError as PatchrightTimeoutError
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from scrapling.engines._browsers._base import StealthySessionMixin

from proprietary.scraping.browser_pool import PooledPage

logger = logging.getLogger(__name__)

# scrapling drives patchright, but a plain playwright page raises its own class.
_TIMEOUTS = (PatchrightTimeoutError, PlaywrightTimeoutError, TimeoutError)
_PAGE_ERRORS = (PatchrightError, PlaywrightError)
# page.content() raises while the clearance reload is in flight ('Execution context
# was destroyed'); scrapling retries it the same way (ResponseFactory).
_CONTENT_TRIES = 10
_CONTENT_RETRY_S = 0.3

# Cheap substrings that gate scrapling's parse-based classifier, so a clean 1 MB
# page costs a scan instead of a DOM parse.
_CF_MARKERS = ("cType: '", "challenges.cloudflare.com/turnstile/v")
_CF_TITLE = "<title>just a moment"


@dataclass
class Landing:
    """Where `goto()` left the page."""

    response: Any | None  # the main document's response; None on a same-page hop
    status: int  # 0 without a response
    headers: dict[str, str]  # lower-cased response headers
    ready: bool  # ready_selector attached in time (True when none was given)
    # ms since the goto started, at the end of each stage, for perf lines
    ms: dict[str, float] = field(default_factory=dict)


async def goto(
    page: Any,
    url: str,
    *,
    wait_until: Literal["commit", "domcontentloaded", "load"] = "domcontentloaded",
    ready_selector: str | None = None,
    ready_timeout_ms: int = 8000,
    idle_cap_ms: int = 0,
    referer: str | None = None,
    commit_timeout_ms: int = 10000,
) -> Landing:
    """Navigate and wait only as long as asked.

    The response must start within `commit_timeout_ms` (a dead exit fails fast),
    then `wait_until` is awaited under the page's default timeout (both raise on
    timeout). `ready_selector` and `idle_cap_ms` are bounded waits that never raise:
    a missing selector is `Landing.ready == False`, an endless page is cut at the cap.
    """
    ms: dict[str, float] = {}
    started = time.perf_counter()

    def lap(stage: str) -> None:
        ms[stage] = round((time.perf_counter() - started) * 1000)

    response = await page.goto(
        url, wait_until="commit", timeout=commit_timeout_ms, referer=referer
    )
    lap("commit")
    if wait_until != "commit":
        await page.wait_for_load_state(wait_until)
        lap(wait_until)
    ready = True
    if ready_selector:
        try:
            await page.wait_for_selector(
                ready_selector, state="attached", timeout=ready_timeout_ms
            )
        except _TIMEOUTS:
            ready = False
        lap("ready")
    if idle_cap_ms > 0:
        await wait_state(page, "networkidle", idle_cap_ms)
        lap("idle")
    headers = dict(response.headers) if response is not None else {}
    return Landing(
        response=response,
        status=response.status if response is not None else 0,
        headers={k.lower(): v for k, v in headers.items()},
        ready=ready,
        ms=ms,
    )


async def wait_state(
    page: Any,
    state: Literal["domcontentloaded", "load", "networkidle"],
    cap_ms: int,
) -> bool:
    """Wait for a load state for at most `cap_ms`; False when the cap ran out."""
    try:
        await page.wait_for_load_state(state, timeout=cap_ms)
    except _TIMEOUTS:
        return False
    return True


def challenge_kind(status: int, headers: Mapping[str, str], html: str) -> str | None:
    """The Cloudflare challenge on a page, or None when it is clean.

    The kinds are scrapling's ('non-interactive', 'managed', 'interactive',
    'embedded'); a challenge seen only in the response ('cf-mitigated: challenge',
    or a 403/503 'Just a moment' page) reads as 'managed'. Pass the whole HTML to
    catch an embedded Turnstile; the first 64 KB is enough for an interstitial.
    """
    if any(marker in html for marker in _CF_MARKERS):
        kind = StealthySessionMixin._detect_cloudflare(html)
        if kind:
            return kind
    lowered = {k.lower(): v for k, v in headers.items()}
    if lowered.get("cf-mitigated", "").lower() == "challenge":
        return "managed"
    if status in (403, 503) and _CF_TITLE in html[:4096].lower():
        return "managed"
    return None


async def solve_challenge(
    pooled: PooledPage, kind: str, *, timeout_s: float = 45.0
) -> bool:
    """Run scrapling's Cloudflare solver on this page; True when the challenge is gone.

    Call it only after `challenge_kind()` found one: on a clean page the solver
    still waits up to 5 s for network idle before noticing.
    """
    page = pooled.page
    started = time.perf_counter()
    try:
        async with asyncio.timeout(timeout_s):
            await pooled._session._cloudflare_solver(page)
    except _TIMEOUTS:  # our cap, or one of the solver's own waits
        logger.warning("[scraping][settle] %s challenge timed out unsolved", kind)
        return False
    await wait_state(page, "domcontentloaded", 5000)
    html = await page_content(page)
    if kind in ("non-interactive", "managed", "interactive", "embedded"):
        cleared = StealthySessionMixin._challenge_cleared(html, kind)
    else:
        cleared = challenge_kind(200, {}, html) is None
    # A challenge seen only in the headers has no cType for scrapling to miss.
    cleared = cleared and _CF_TITLE not in html[:4096].lower()
    logger.info(
        "[scraping][settle][perf] solve kind=%s cleared=%s solve_ms=%.0f",
        kind,
        cleared,
        (time.perf_counter() - started) * 1000,
    )
    return cleared


async def page_content(page: Any) -> str:
    """`page.content()`, retried for up to 3 s while a navigation is in flight."""
    for _ in range(_CONTENT_TRIES - 1):
        try:
            return await page.content() or ""
        except _PAGE_ERRORS:
            if page.is_closed():
                raise
        await asyncio.sleep(_CONTENT_RETRY_S)
    return await page.content() or ""
