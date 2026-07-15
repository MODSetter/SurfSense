"""Browser-session fetch seam for the Indeed scraper.

Indeed fronts its origin with Cloudflare plus an anonymous-bot check that bounces
cold sessions to ``secure.indeed.com/auth``. The working recipe: a persistent
camoufox session that solves Cloudflare, warms on the domain home page, then
navigates to ``/jobs`` in the same context so the clearance carries.

:class:`IndeedSession` warms per domain once, retries a blocked page on a fresh
residential IP, and caps each navigation with a hard timeout so a stuck solve
can't stall a run. All egress is through the residential proxy.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import urlparse

from app.utils.proxy import get_proxy_url

logger = logging.getLogger(__name__)


class IndeedAccessBlockedError(RuntimeError):
    """Every rotated IP was bounced to Indeed's security wall."""


# Per navigation; a stuck Cloudflare solve otherwise hangs the whole run.
_PAGE_TIMEOUT_S = 75.0
# Browser-internal timeout; kept above the page timeout so ours fires first.
_SESSION_TIMEOUT_MS = 90_000
_MAX_ROTATIONS = 3

# Markers of a Cloudflare / security-check interstitial served instead of jobs.
_BLOCK_MARKERS = (
    "secure.indeed.com",
    "bot-detection",
    "security check",
    "challenge-platform",
    "just a moment",
    "verify you are human",
    "hcaptcha",
)


def now_iso() -> str:
    """UTC timestamp in the millisecond ISO shape used by scraper output."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class _Session(Protocol):
    """Minimal browser-session surface used here (real or fake)."""

    async def start(self) -> Any: ...
    async def fetch(self, url: str, **kwargs: Any) -> Any: ...
    async def close(self) -> Any: ...


def _default_session_factory() -> _Session:
    """Build a proxied, Cloudflare-solving camoufox session.

    ``disable_resources`` skips images/fonts/media; job data is inline in the
    document, so this only trims bandwidth.
    """
    from scrapling.fetchers import AsyncStealthySession

    return AsyncStealthySession(
        headless=True,
        solve_cloudflare=True,
        network_idle=True,
        block_webrtc=True,
        disable_resources=True,
        timeout=_SESSION_TIMEOUT_MS,
        proxy=get_proxy_url(),
    )


def _html(page: Any) -> str:
    """Best-effort HTML body across scrapling response shapes."""
    for attr in ("html_content", "body", "text"):
        val = getattr(page, attr, None)
        if isinstance(val, bytes):
            val = val.decode("utf-8", "replace")
        if isinstance(val, str) and val:
            return val
    return ""


def _looks_blocked(html: str, final_url: str) -> bool:
    """Whether a response is an interstitial rather than a real page."""
    if not html:
        return True
    haystack = (final_url + " " + html[:6000]).lower()
    return any(marker in haystack for marker in _BLOCK_MARKERS)


class IndeedSession:
    """One warmed browser session that rotates its exit IP when blocked."""

    def __init__(
        self, session_factory: Callable[[], _Session] = _default_session_factory
    ) -> None:
        self._factory = session_factory
        self._session: _Session | None = None
        self._warmed: set[str] = set()
        self.rotations = 0

    async def start(self) -> None:
        self._session = self._factory()
        await self._session.start()

    async def close(self) -> None:
        if self._session is not None:
            with suppress(Exception):
                await self._session.close()
            self._session = None
        self._warmed.clear()

    async def _rotate(self) -> None:
        """Drop the session for a fresh exit IP; clears warmed domains."""
        await self.close()
        self.rotations += 1
        await self.start()
        logger.info("[indeed] rotated session (rotation #%d)", self.rotations)

    async def _timed_fetch(self, url: str, **kwargs: Any) -> Any:
        assert self._session is not None
        coro: Awaitable[Any] = self._session.fetch(url, **kwargs)
        return await asyncio.wait_for(coro, timeout=_PAGE_TIMEOUT_S)

    async def _ensure_warm(self, domain: str) -> None:
        """Land on the domain home with a Google referer before scraping it."""
        if domain in self._warmed:
            return
        with suppress(Exception):
            await self._timed_fetch(f"https://{domain}/", google_search=True)
        self._warmed.add(domain)

    async def fetch_html(self, url: str, *, max_rotations: int | None = None) -> str:
        """Return a search/company/job page's HTML through the warmed session.

        Rotates the IP and re-warms on a security-wall bounce or timeout; raises
        :class:`IndeedAccessBlockedError` once rotations are exhausted. ``max_rotations``
        overrides the default budget: pass ``0`` to fail fast on a systematically
        gated page (e.g. anonymous pagination) instead of burning rotations on a
        block no fresh IP will clear.
        """
        if self._session is None:
            await self.start()
        budget = _MAX_ROTATIONS if max_rotations is None else max_rotations
        domain = urlparse(url).hostname or "www.indeed.com"
        attempt = 0
        while True:
            try:
                await self._ensure_warm(domain)
                page = await self._timed_fetch(url)
                html = _html(page)
                if not _looks_blocked(html, str(getattr(page, "url", "") or "")):
                    return html
                logger.info("[indeed] blocked on %s", url)
            except TimeoutError:
                logger.warning("[indeed] fetch timed out on %s", url)
            except Exception as e:
                logger.warning("[indeed] fetch failed on %s: %s", url, e)

            if attempt >= budget:
                raise IndeedAccessBlockedError(
                    f"Indeed refused {url} after {attempt + 1} attempt(s)"
                )
            attempt += 1
            await self._rotate()


@asynccontextmanager
async def open_session(
    session_factory: Callable[[], _Session] = _default_session_factory,
):
    """Open an :class:`IndeedSession` and guarantee teardown."""
    session = IndeedSession(session_factory)
    await session.start()
    try:
        yield session
    finally:
        await session.close()
