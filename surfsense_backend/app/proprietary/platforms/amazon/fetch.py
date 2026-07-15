"""Network access for public Amazon pages.

All requests use the configured residential proxy. Responses that contain an
anti-bot interstitial are retried with a fresh proxy exit, while ordinary HTTP
failures are returned to the caller for domain-specific error handling.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from scrapling.fetchers import AsyncFetcher

from app.utils.proxy import get_proxy_url

logger = logging.getLogger(__name__)

_MAX_IP_ATTEMPTS = 8
_REQUEST_TIMEOUT_S = 30
_HEADERS = {
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
}
_BLOCK_MARKERS = (
    "/errors/validatecaptcha",
    "api-services-support@amazon.com",
    "robot check",
    "enter the characters you see below",
)
_CSRF_PATTERNS = (
    re.compile(
        r"""(?:name|id)=["'](?:anti-csrftoken-a2z|csrf-token)["'][^>]*"""
        r"""(?:value|content)=["']([^"']+)""",
        re.IGNORECASE,
    ),
    re.compile(
        r"""["'](?:anti-csrftoken-a2z|csrf-token)["']\s*[:=]\s*["']([^"']+)""",
        re.IGNORECASE,
    ),
)


@dataclass(frozen=True)
class FetchResult:
    """The response details needed by scraper flows."""

    status: int
    html: str
    url: str
    cookies: dict[str, str]


@dataclass
class LocationSession:
    """Anonymous delivery-location state pinned to one proxy exit."""

    proxy: str | None
    cookies: dict[str, str]
    country_code: str | None
    zip_code: str
    location_text: str | None
    created_at: float


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


def is_blocked(html: str | None, status: int) -> bool:
    """Return whether a response is an Amazon anti-bot interstitial.

    ``202`` is a soft anti-bot response Amazon serves to some proxy exits (an
    empty/accepted body rather than the page), so it is treated as blocked and
    retried on a fresh exit rather than parsed as a real page.
    """
    if status in {202, 429, 503}:
        return True
    text = (html or "")[:200_000].lower()
    return any(marker in text for marker in _BLOCK_MARKERS)


def _response_url(page: Any, fallback: str) -> str:
    value = getattr(page, "url", None)
    return str(value) if value else fallback


def _response_cookies(page: Any) -> dict[str, str]:
    cookies = getattr(page, "cookies", None)
    return dict(cookies) if isinstance(cookies, dict) else {}


async def fetch_page(
    url: str,
    *,
    cookies: dict[str, str] | None = None,
    proxy: str | None = None,
    method: str = "GET",
    data: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    rotate_on_block: bool = True,
) -> FetchResult | None:
    """Fetch a page and retry blocked responses with fresh proxy exits."""
    attempts = _MAX_IP_ATTEMPTS if rotate_on_block else 1
    for attempt in range(1, attempts + 1):
        selected_proxy = proxy if proxy is not None else get_proxy_url()
        started = time.perf_counter()
        try:
            request = AsyncFetcher.post if method == "POST" else AsyncFetcher.get
            kwargs: dict[str, Any] = {
                "headers": {**_HEADERS, **(headers or {})},
                "cookies": cookies or {},
                "proxy": selected_proxy,
                "stealthy_headers": True,
                "timeout": _REQUEST_TIMEOUT_S,
            }
            if method == "POST":
                kwargs["data"] = data or {}
            page = await request(url, **kwargs)
        except Exception as exc:
            logger.warning("Amazon request failed for %s: %s", url, exc)
            if proxy is not None:
                return None
            continue

        status = int(getattr(page, "status", 0) or 0)
        html = getattr(page, "html_content", None) or ""
        logger.info(
            "[amazon][perf] method=%s status=%s attempt=%s fetch_ms=%.1f url=%s",
            method,
            status,
            attempt,
            (time.perf_counter() - started) * 1000,
            url,
        )
        if rotate_on_block and is_blocked(html, status):
            logger.info(
                "Amazon blocked proxy attempt %s/%s for %s", attempt, attempts, url
            )
            continue
        return FetchResult(
            status=status,
            html=html,
            url=_response_url(page, url),
            cookies=_response_cookies(page),
        )
    logger.warning("Amazon exhausted %s proxy attempts for %s", attempts, url)
    return None


async def fetch_html(
    url: str,
    *,
    cookies: dict[str, str] | None = None,
    proxy: str | None = None,
) -> str | None:
    """Return public page HTML, or ``None`` when no usable response is obtained."""
    result = await fetch_page(url, cookies=cookies, proxy=proxy)
    return result.html if result is not None and result.status == 200 else None


async def resolve_shortlink(url: str) -> str | None:
    """Follow a shortened Amazon URL and return its final destination."""
    result = await fetch_page(url)
    return result.url if result is not None and result.status == 200 else None


def _origin(domain: str) -> str:
    return f"https://{domain}"


def _csrf_token(html: str) -> str | None:
    for pattern in _CSRF_PATTERNS:
        match = pattern.search(html)
        if match:
            return match.group(1)
    return None


async def fetch_aod_html(
    asin: str,
    domain: str,
    *,
    cookies: dict[str, str] | None = None,
    proxy: str | None = None,
) -> str | None:
    """Fetch the public all-offers panel for one product.

    ``aodAjaxMain`` is a path segment, not a query param. Amazon also serves this
    panel as a JS-only modal for many (especially US) ASINs, so a 404 here is
    expected and the caller falls back to the PDP buy-box winner.
    """
    url = f"{_origin(domain)}/gp/product/ajax/aodAjaxMain/?asin={asin}"
    return await fetch_html(url, cookies=cookies, proxy=proxy)


async def fetch_seller_html(
    seller_id: str,
    domain: str,
    *,
    cookies: dict[str, str] | None = None,
    proxy: str | None = None,
) -> str | None:
    """Fetch a public seller profile."""
    return await fetch_html(
        f"{_origin(domain)}/sp?seller={seller_id}", cookies=cookies, proxy=proxy
    )


_LOCATION_SESSION_TTL_S = 30 * 60
_location_sessions: dict[tuple[str, str, str | None], LocationSession] = {}
_location_locks: dict[tuple[str, str, str | None], asyncio.Lock] = {}


def should_localize(route: str, deliverable_routes: list[str] | None) -> bool:
    """Return whether a request route should use delivery-location state."""
    return route.upper() in {value.upper() for value in (deliverable_routes or [])}


async def _sticky_proxy(session_id: str) -> str | None:
    """Request a stable proxy exit when the active provider supports it."""
    try:
        from app.utils.proxy import get_sticky_proxy_url

        return get_sticky_proxy_url(session_id)
    except (ImportError, NotImplementedError):
        return get_proxy_url()


async def get_location_session(
    domain: str,
    *,
    zip_code: str,
    country_code: str | None,
) -> LocationSession | None:
    """Create or reuse an anonymous delivery-location session."""
    key = (domain, zip_code, country_code)
    cached = _location_sessions.get(key)
    if cached and time.time() - cached.created_at < _LOCATION_SESSION_TTL_S:
        return cached

    lock = _location_locks.setdefault(key, asyncio.Lock())
    async with lock:
        cached = _location_sessions.get(key)
        if cached and time.time() - cached.created_at < _LOCATION_SESSION_TTL_S:
            return cached

        session_id = f"amazon-{abs(hash(key)) & 0xFFFFFFFF:x}"
        proxy = await _sticky_proxy(session_id)
        home = await fetch_page(
            f"{_origin(domain)}/?ref_=nav_logo",
            proxy=proxy,
            rotate_on_block=False,
        )
        if home is None or home.status != 200:
            return None
        csrf = _csrf_token(home.html)
        if csrf is None:
            logger.warning("Amazon location session did not expose a CSRF token")
            return None

        endpoint = f"{_origin(domain)}/gp/delivery/ajax/address-change.html"
        payload = {
            "locationType": "LOCATION_INPUT",
            "zipCode": zip_code,
            "storeContext": "generic",
            "deviceType": "web",
            "pageType": "Gateway",
            "actionSource": "glow",
        }
        cookies = dict(home.cookies)
        cookies["anti-csrftoken-a2z"] = csrf
        changed = await fetch_page(
            endpoint,
            cookies=cookies,
            proxy=proxy,
            method="POST",
            data=payload,
            headers={
                "anti-csrftoken-a2z": csrf,
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            },
            rotate_on_block=False,
        )
        if changed is None or changed.status != 200:
            return None
        cookies.update(changed.cookies)
        location_text = zip_code
        session = LocationSession(
            proxy=proxy,
            cookies=cookies,
            country_code=country_code.upper() if country_code else None,
            zip_code=zip_code,
            location_text=location_text,
            created_at=time.time(),
        )
        _location_sessions[key] = session
        return session
