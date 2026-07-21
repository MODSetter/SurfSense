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

``ponytail:`` MVP hits only the server-rendered ``__NEXT_DATA__`` pages, which
TLS impersonation + residential proxies clear without seeding PerimeterX cookies.
If block rates on those pages climb, the upgrade path is a warmed sticky session
(seed ``_px3``/``_pxhd``/``ACID`` from a homepage fetch, reuse exit + cookies) —
the same shape as Amazon's ``get_location_session``.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from scrapling.fetchers import AsyncFetcher

from app.utils.proxy import get_geo_proxy_url, get_sticky_proxy_url

logger = logging.getLogger(__name__)

_MAX_IP_ATTEMPTS = 6
_REQUEST_TIMEOUT_S = 30
_HEADERS = {
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
_BLOCK_MARKERS = (
    "robot or human",
    "px-captcha",
    "/blocked",
    "verify you are a human",
    "access to this page has been denied",
)


@dataclass(frozen=True)
class FetchResult:
    """The response details needed by scraper flows."""

    status: int
    html: str
    url: str
    cookies: dict[str, str]
    headers: dict[str, str] = field(default_factory=dict)


async def gather_bounded[T](
    factories: list[Callable[[], Awaitable[T]]], *, concurrency: int
) -> list[T]:
    """Run async factories concurrently while preserving input order."""
    if not factories:
        return []
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def run(factory: Callable[[], Awaitable[T]]) -> T:
        async with semaphore:
            return await factory()

    return await asyncio.gather(*(run(factory) for factory in factories))


def is_blocked(
    html: str | None, status: int, headers: dict[str, str] | None = None
) -> bool:
    """Return whether a response is a Walmart anti-bot interstitial.

    ``412`` is PerimeterX's rejection; ``429``/``503`` are throttles. Walmart also
    serves CAPTCHA with a ``200`` body, so the body is scanned regardless of
    status.
    """
    if status in {412, 429, 503}:
        return True
    text = (html or "")[:200_000].lower()
    return any(marker in text for marker in _BLOCK_MARKERS)


def _response_url(page: Any, fallback: str) -> str:
    value = getattr(page, "url", None)
    return str(value) if value else fallback


def _response_cookies(page: Any) -> dict[str, str]:
    cookies = getattr(page, "cookies", None)
    return dict(cookies) if isinstance(cookies, dict) else {}


def _response_headers(page: Any) -> dict[str, str]:
    headers = getattr(page, "headers", None)
    return dict(headers) if isinstance(headers, dict) else {}


def _selected_proxy(
    proxy: str | None, country: str, attempt: int, url: str
) -> str | None:
    if proxy is not None:
        return proxy
    if attempt > 1:
        session_id = f"walmart-{attempt}-{abs(hash((url, time.time_ns()))):x}"
        return get_sticky_proxy_url(session_id, country)
    return get_geo_proxy_url(country)


async def fetch_page(
    url: str,
    *,
    cookies: dict[str, str] | None = None,
    proxy: str | None = None,
    country: str = "us",
    rotate_on_block: bool = True,
) -> FetchResult | None:
    """Fetch a page and retry blocked responses with fresh proxy exits."""
    attempts = _MAX_IP_ATTEMPTS if rotate_on_block else 1
    for attempt in range(1, attempts + 1):
        selected_proxy = _selected_proxy(proxy, country, attempt, url)
        started = time.perf_counter()
        try:
            page = await AsyncFetcher.get(
                url,
                headers={**_HEADERS},
                cookies=cookies or {},
                proxy=selected_proxy,
                stealthy_headers=True,
                timeout=_REQUEST_TIMEOUT_S,
            )
        except Exception as exc:
            logger.warning("Walmart request failed for %s: %s", url, exc)
            if proxy is not None:
                return None
            continue

        status = int(getattr(page, "status", 0) or 0)
        html = getattr(page, "html_content", None) or ""
        response_headers = _response_headers(page)
        logger.info(
            "[walmart][perf] status=%s attempt=%s fetch_ms=%.1f url=%s",
            status,
            attempt,
            (time.perf_counter() - started) * 1000,
            url,
        )
        if rotate_on_block and is_blocked(html, status, response_headers):
            logger.info(
                "Walmart blocked proxy attempt %s/%s for %s", attempt, attempts, url
            )
            continue
        return FetchResult(
            status=status,
            html=html,
            url=_response_url(page, url),
            cookies=_response_cookies(page),
            headers=response_headers,
        )
    logger.warning("Walmart exhausted %s proxy attempts for %s", attempts, url)
    return None
