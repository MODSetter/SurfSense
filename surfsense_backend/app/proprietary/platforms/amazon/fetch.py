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
from dataclasses import dataclass, field
from typing import Any

from scrapling.fetchers import AsyncFetcher

from app.utils.proxy import get_geo_proxy_url, get_sticky_proxy_url

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
    "token.awswaf.com",
    "/challenge.js",
    "awswafintegration",
    "bm-verify=",
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
    headers: dict[str, str] = field(default_factory=dict)


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


def is_blocked(
    html: str | None, status: int, headers: dict[str, str] | None = None
) -> bool:
    """Return whether a response is an Amazon anti-bot interstitial.

    ``202`` is a soft anti-bot response Amazon serves to some proxy exits (an
    empty/accepted body rather than the page), so it is treated as blocked and
    retried on a fresh exit rather than parsed as a real page.
    """
    if status in {202, 429, 503}:
        return True
    if _header_value(headers, "x-amzn-waf-action") == "challenge":
        return True
    text = (html or "")[:200_000].lower()
    return any(marker in text for marker in _BLOCK_MARKERS)


def _header_value(headers: dict[str, str] | None, name: str) -> str | None:
    if not headers:
        return None
    needle = name.lower()
    for key, value in headers.items():
        if key.lower() == needle:
            return str(value).strip().lower()
    return None


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
    proxy: str | None, country: str | None, attempt: int, url: str
) -> str | None:
    if proxy is not None:
        return proxy
    if country and attempt > 1:
        session_id = f"amazon-{country}-{attempt}-{abs(hash((url, time.time_ns()))):x}"
        return get_sticky_proxy_url(session_id, country)
    return get_geo_proxy_url(country)


async def fetch_page(
    url: str,
    *,
    cookies: dict[str, str] | None = None,
    proxy: str | None = None,
    country: str | None = None,
    accept_language: str | None = None,
    method: str = "GET",
    data: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    rotate_on_block: bool = True,
) -> FetchResult | None:
    """Fetch a page and retry blocked responses with fresh proxy exits."""
    attempts = _MAX_IP_ATTEMPTS if rotate_on_block else 1
    for attempt in range(1, attempts + 1):
        selected_proxy = _selected_proxy(proxy, country, attempt, url)
        started = time.perf_counter()
        try:
            request = AsyncFetcher.post if method == "POST" else AsyncFetcher.get
            request_headers = {**_HEADERS}
            if accept_language:
                request_headers["Accept-Language"] = (
                    f"{accept_language},{accept_language.split('-', 1)[0]};q=0.9"
                )
            request_headers.update(headers or {})
            kwargs: dict[str, Any] = {
                "headers": request_headers,
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
        response_headers = _response_headers(page)
        logger.info(
            "[amazon][perf] method=%s status=%s attempt=%s fetch_ms=%.1f url=%s",
            method,
            status,
            attempt,
            (time.perf_counter() - started) * 1000,
            url,
        )
        if rotate_on_block and is_blocked(html, status, response_headers):
            logger.info(
                "Amazon blocked proxy attempt %s/%s for %s", attempt, attempts, url
            )
            continue
        return FetchResult(
            status=status,
            html=html,
            url=_response_url(page, url),
            cookies=_response_cookies(page),
            headers=response_headers,
        )
    logger.warning("Amazon exhausted %s proxy attempts for %s", attempts, url)
    return None


async def fetch_html(
    url: str,
    *,
    cookies: dict[str, str] | None = None,
    proxy: str | None = None,
    country: str | None = None,
    accept_language: str | None = None,
) -> str | None:
    """Return public page HTML, or ``None`` when no usable response is obtained."""
    result = await fetch_page(
        url,
        cookies=cookies,
        proxy=proxy,
        country=country,
        accept_language=accept_language,
    )
    return result.html if result is not None and result.status == 200 else None


async def resolve_shortlink(
    url: str, *, country: str | None = None, accept_language: str | None = None
) -> str | None:
    """Follow a shortened Amazon URL and return its final destination."""
    result = await fetch_page(
        url, country=country, accept_language=accept_language
    )
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
    country: str | None = None,
    accept_language: str | None = None,
) -> str | None:
    """Fetch the public all-offers panel for one product.

    ``aodAjaxMain`` is a path segment, not a query param. Amazon also serves this
    panel as a JS-only modal for many (especially US) ASINs, so a 404 here is
    expected and the caller falls back to the PDP buy-box winner.
    """
    url = f"{_origin(domain)}/gp/product/ajax/aodAjaxMain/?asin={asin}"
    return await fetch_html(
        url,
        cookies=cookies,
        proxy=proxy,
        country=country,
        accept_language=accept_language,
    )


async def fetch_seller_html(
    seller_id: str,
    domain: str,
    *,
    cookies: dict[str, str] | None = None,
    proxy: str | None = None,
    country: str | None = None,
    accept_language: str | None = None,
) -> str | None:
    """Fetch a public seller profile."""
    return await fetch_html(
        f"{_origin(domain)}/sp?seller={seller_id}",
        cookies=cookies,
        proxy=proxy,
        country=country,
        accept_language=accept_language,
    )


_LOCATION_SESSION_TTL_S = 30 * 60
_location_sessions: dict[tuple[str, str, str | None], LocationSession] = {}
_location_locks: dict[tuple[str, str, str | None], asyncio.Lock] = {}


def should_localize(route: str, deliverable_routes: list[str] | None) -> bool:
    """Return whether a request route should use delivery-location state."""
    return route.upper() in {value.upper() for value in (deliverable_routes or [])}


async def _sticky_proxy(session_id: str, country: str | None = None) -> str | None:
    """Request a stable proxy exit when the active provider supports it."""
    try:
        return get_sticky_proxy_url(session_id, country)
    except (ImportError, NotImplementedError):
        return get_geo_proxy_url(country)


async def get_location_session(
    domain: str,
    *,
    zip_code: str,
    country_code: str | None,
    country: str | None = None,
    accept_language: str | None = None,
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
        proxy = await _sticky_proxy(session_id, country)
        home = await fetch_page(
            f"{_origin(domain)}/?ref_=nav_logo",
            proxy=proxy,
            country=country,
            accept_language=accept_language,
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
            country=country,
            accept_language=accept_language,
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
