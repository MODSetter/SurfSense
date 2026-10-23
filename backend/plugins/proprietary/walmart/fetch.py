"""Network access for public Walmart pages.

Mirrors the Amazon fetch layer: every request goes through the configured
residential proxy (pinned to the US, since Walmart geo-locks inventory), and any
response that looks like an anti-bot interstitial is retried on a fresh proxy
exit. Ordinary HTTP failures are returned to the caller for domain-specific
handling.

Walmart runs Akamai (edge/TLS) + PerimeterX/HUMAN (behavioral JS). Two Walmart
specifics differ from Amazon:

* Walmart serves CAPTCHA with an HTTP ``200`` body ("Robot or human?"), so block
  detection scans the body, never the status alone.
* ``412`` is PerimeterX's rejection code and is treated as blocked → rotate.

Requests go through the shared fail-fast transport (``scraping.http``): one try
per exit with no hidden retries, a ``(4, 12)`` s timeout, redirects followed by
hand so a redirect to ``/blocked`` fails at once, and a hedge on a fresh exit
when a try is slower than nearly all others.

``ponytail:`` MVP hits only the server-rendered ``__NEXT_DATA__`` pages, which
TLS impersonation + residential proxies clear without seeding PerimeterX cookies.
If block rates on those pages climb, the upgrade path is a warmed sticky session
(seed ``_px3``/``_pxhd``/``ACID`` from a homepage fetch, reuse exit + cookies) —
the same shape as Amazon's ``get_location_session``.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit

from proprietary.scraping import http, sessions
from proprietary.scraping.concurrency import hedged
from proprietary.scraping.logged_host import logged_host

logger = logging.getLogger(__name__)

_MAX_IP_ATTEMPTS = 4
# No new try starts past this; a try in flight is cut off at it.
_PAGE_BUDGET_S = 25.0
# CONNECT + TLS took up to ~1.05 s (p99), so 4 s only cuts dead exits; the whole
# request is capped at 16 s, where a 30 s timeout plus retries once stalled 64 s.
_TIMEOUT = (4.0, 12.0)
# /ip/{id} answers with a redirect to its slug page; one more hop is slack.
_MAX_FOLLOWS = 2
# Past these a try is slower than ~90% of tries, so a second exit races it.
PRODUCT_HEDGE_S = 4.0
REVIEWS_HEDGE_S = 3.5
_HEADERS = {
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
_BLOCK_STATUSES = frozenset({403, 412, 429, 444, 503})
_BLOCK_MARKERS = (
    "robot or human",
    "px-captcha",
    "/blocked",
    "verify you are a human",
    "access to this page has been denied",
)
_BLOCK_MARKER_BYTES = tuple(marker.encode() for marker in _BLOCK_MARKERS)
_BLOCK_SCAN_BYTES = 200_000

# The caller's stage reporter, inherited by every task a fetch runs in.
_reporter: ContextVar[Callable[[str], Awaitable[None]] | None] = ContextVar(
    "walmart_reporter", default=None
)


@dataclass(frozen=True)
class FetchResult:
    """The response details needed by scraper flows."""

    status: int
    html: str
    url: str
    cookies: dict[str, str]
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class _Refused:
    """Why one try yielded no page; the rotation loop tries a fresh exit."""

    reason: str


@contextmanager
def reporting(report: Callable[[str], Awaitable[None]] | None) -> Iterator[None]:
    """Send each fetch's stages (try started, page fetched) to ``report``."""
    token = _reporter.set(report)
    try:
        yield
    finally:
        _reporter.reset(token)


async def _report(message: str) -> None:
    report = _reporter.get()
    if report is not None:
        await report(message)


def _blocked(response: http.RawResponse) -> bool:
    """Return whether a response is a Walmart anti-bot interstitial.

    ``412`` is PerimeterX's rejection; ``429``/``503`` are throttles; ``403`` and
    ``444`` are the edge turning the exit away; a redirect to ``/blocked`` is
    the captcha page. Walmart also serves CAPTCHA with a ``200`` body, so the
    body is scanned regardless of status, as bytes, so no page is decoded on
    the event loop to test it.
    """
    if response.status in _BLOCK_STATUSES:
        return True
    if 300 <= response.status < 400:
        # The path, not a substring: a product slug may start with "blocked".
        target = _redirect(response)
        return target is not None and urlsplit(target).path.startswith("/blocked")
    if urlsplit(response.url).path.startswith("/blocked"):
        return True
    head = response.body[:_BLOCK_SCAN_BYTES].lower()
    return any(marker in head for marker in _BLOCK_MARKER_BYTES)


def _redirect(response: http.RawResponse) -> str | None:
    location = response.location() if 300 <= response.status < 400 else None
    return urljoin(response.url, location) if location else None


async def _try(
    url: str,
    *,
    stage: str,
    attempt: int,
    fresh: bool,
    country: str,
    cookies: dict[str, str] | None,
) -> FetchResult | _Refused:
    """One try on an exit of its own: the page, or why another exit should try."""
    # The first try takes the rotating gateway; retries and hedges each lease a
    # sticky exit, so no two share an IP and a refused one sits out a while.
    exit = sessions.lease_exit("walmart", country) if fresh else sessions.Exit(country)
    refused = True
    try:
        # One session per try: the redirect hop rides its connection (same IP)
        # and carries the cookies the first hop set, as curl's own follow did.
        async with sessions.holder("walmart", exit, max_streams=1) as h:
            target: str | None = url
            for _ in range(_MAX_FOLLOWS + 1):
                if target is None:
                    break
                response = await h.request(
                    "GET",
                    target,
                    stage=stage,
                    headers=_HEADERS,
                    cookies=cookies,
                    timeout=_TIMEOUT,
                    allow_redirects=False,
                    attempt=attempt,
                    is_blocked=_blocked,
                )
                target = None if response.blocked else _redirect(response)
    except http.TransportError as exc:
        logger.warning(
            "Walmart request failed for %s: %s %s",
            logged_host(url),
            exc.kind,
            exc.detail,
        )
        return _Refused(exc.kind)
    else:
        if response.blocked:
            return _Refused(f"blocked (status {response.status})")
        if target is not None:
            # Still redirecting after the last hop: its empty body is no page.
            logger.info(
                "Walmart redirects for %s went past %s hops",
                logged_host(url),
                _MAX_FOLLOWS,
            )
            return _Refused(f"too many redirects (status {response.status})")
        if response.status >= 500:
            # A transient edge error (seen: 520 mid-way through review pages)
            # would otherwise read as an empty page and end the pagination.
            return _Refused(f"server error {response.status}")
        refused = False
        # Decoding a 1.4 MB search page would hold the loop a few ms.
        html = await asyncio.to_thread(response.text)
        return FetchResult(
            status=response.status,
            html=html,
            url=response.url,
            cookies=response.cookies,
            headers=dict(response.headers),
        )
    finally:
        sessions.release_exit(exit, burned=refused)


async def fetch_page(
    url: str,
    *,
    cookies: dict[str, str] | None = None,
    country: str = "us",
    stage: str = "page",
    hedge_after_s: float = PRODUCT_HEDGE_S,
) -> FetchResult | None:
    """Fetch a page and retry blocked responses with fresh proxy exits.

    Each try past ``hedge_after_s`` races a second exit; at most
    ``_MAX_IP_ATTEMPTS`` tries and ``_PAGE_BUDGET_S`` in all, then ``None``.
    """
    try:
        async with asyncio.timeout(_PAGE_BUDGET_S):
            for attempt in range(_MAX_IP_ATTEMPTS):
                await _report(f"fetching a {stage} page (try {attempt + 1})")
                outcome = await hedged(
                    lambda i, attempt=attempt: _try(
                        url,
                        stage=stage,
                        attempt=attempt,
                        fresh=attempt > 0 or i > 0,
                        country=country,
                        cookies=cookies,
                    ),
                    after_s=hedge_after_s,
                    accept=lambda outcome: isinstance(outcome, FetchResult),
                    plugin="walmart",
                    stage=stage,
                )
                if isinstance(outcome, FetchResult):
                    await _report(f"fetched a {stage} page")
                    return outcome
                if outcome.reason.startswith("server error"):
                    logger.info(
                        "Walmart %s on proxy attempt %s/%s for %s",
                        outcome.reason,
                        attempt + 1,
                        _MAX_IP_ATTEMPTS,
                        logged_host(url),
                    )
                elif outcome.reason.startswith("blocked"):
                    logger.info(
                        "Walmart blocked proxy attempt %s/%s for %s",
                        attempt + 1,
                        _MAX_IP_ATTEMPTS,
                        logged_host(url),
                    )
    except TimeoutError:
        logger.warning(
            "Walmart gave up on %s after %.0f s", logged_host(url), _PAGE_BUDGET_S
        )
        return None
    logger.warning(
        "Walmart exhausted %s proxy attempts for %s",
        _MAX_IP_ATTEMPTS,
        logged_host(url),
    )
    return None
