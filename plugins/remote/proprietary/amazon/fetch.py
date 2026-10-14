"""Network access for public Amazon pages.

All requests use the configured residential proxy. Responses that contain an
anti-bot interstitial are retried with a fresh proxy exit, while ordinary HTTP
failures are returned to the caller for domain-specific error handling.
"""

from __future__ import annotations

import asyncio
import html as html_lib
import logging
import os
import re
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

from proprietary.scraping import http, sessions
from proprietary.scraping.concurrency import hedged
from proprietary.scraping.proxy import get_geo_proxy_url

from .url_resolver import resolve_url

logger = logging.getLogger(__name__)

_MAX_IP_ATTEMPTS = 8
# Kill switch for the per-route referer: =0 sends scrapling's Google referer on
# every request again. Search pages drew 10/10 blocks with it, 3/10 without.
_NO_GOOGLE_REFERER_ENV = "AMAZON_NO_GOOGLE_REFERER"
# Kill switch for hedging (AZ-2): =0 sends one request per attempt again.
_HEDGE_ENV = "AMAZON_HEDGE"
# Kill switch for the offers panel's XHR shape (page referer, X-Requested-With):
# =0 sends it the Google referer again. Its own switch, as it was never gated.
_AOD_XHR_ENV = "AMAZON_AOD_XHR"
# (connect incl. proxy CONNECT and TLS, read); the largest healthy PDP took 6.3 s.
_TIMEOUT = (4.0, 12.0)
# A hedge starts once an attempt outlives about the healthy p90 of its route.
_HEDGE_AFTER_S = {"pdp": 5.0}
_DEFAULT_HEDGE_AFTER_S = 3.0
_HEDGES_PER_CALL = 3
# Shortener hops followed by hand, so the target page is not downloaded twice.
_SHORTLINK_HOPS = 5
_SHORTLINK_TARGETS = frozenset({"product", "search", "bestsellers"})
# Location cookies are bound to one sticky IP: a few requests at a time on it.
_LOCATION_EXIT_CONCURRENCY = 3
# Exits tried to set a location, and attempts on location sessions per request.
_LOCATION_TRIES = 3
_LOCATION_FAILURE_TTL_S = 5 * 60
# Decoding a body this large takes a few ms, so it goes to a thread.
_LARGE_BODY = 1_000_000
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
_BLOCK_MARKER_BYTES = tuple(marker.encode() for marker in _BLOCK_MARKERS)
_CSRF_PATTERNS = (
    re.compile(
        r"""(?:name|id)=["'](?:anti-csrftoken-a2z|csrf-token)["'][^>]*"""
        r"""(?:value|content)=["']([^"']+)""",
        re.IGNORECASE,
    ),
    re.compile(
        r"""["'](?:anti-csrftoken-a2z|csrf-token|CSRF_TOKEN)["']\s*[:=]\s*["']([^"']+)""",
        re.IGNORECASE,
    ),
    re.compile(r"""\bCSRF_TOKEN\s*:\s*["']([^"']+)"""),
)

# Per call (set by the scraper): hedges left, and notes for the tool's summary.
_hedges_left: ContextVar[list[int] | None] = ContextVar(
    "amazon_hedges_left", default=None
)
_notes: ContextVar[list[str] | None] = ContextVar("amazon_notes", default=None)


@dataclass(frozen=True)
class FetchResult:
    """The response details needed by scraper flows."""

    status: int
    html: str
    url: str
    cookies: dict[str, str]
    headers: dict[str, str] = field(default_factory=dict)
    # The delivery-location session the page was fetched on, if one held.
    location: LocationSession | None = None


@dataclass
class LocationSession:
    """Anonymous delivery-location state pinned to one proxy exit."""

    proxy: str | None
    cookies: dict[str, str]
    country_code: str | None
    zip_code: str
    location_text: str | None
    created_at: float
    exit: sessions.Exit | None = None
    key: tuple[str, str, str | None] | None = None
    slots: asyncio.Semaphore = field(
        default_factory=lambda: asyncio.Semaphore(_LOCATION_EXIT_CONCURRENCY)
    )


class _NoHedgeLeftError(Exception):
    """This call already started its hedges; the primary attempt runs alone."""


def start_call() -> tuple[list[str], Any, Any]:
    """Give the current call its hedge budget and an empty notes list.

    Returns the notes and the tokens :func:`end_call` resets.
    """
    notes: list[str] = []
    budget = [0 if os.environ.get(_HEDGE_ENV, "1").strip() == "0" else _HEDGES_PER_CALL]
    return notes, _hedges_left.set(budget), _notes.set(notes)


def end_call(hedges_token: Any, notes_token: Any) -> None:
    _hedges_left.reset(hedges_token)
    _notes.reset(notes_token)


def note(message: str) -> None:
    """Tell the caller about something it asked for that could not be done."""
    notes = _notes.get()
    if notes is not None and message not in notes:
        notes.append(message)


def is_blocked(html: str | bytes | None, status: int, headers: Any = None) -> bool:
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
    markers = _BLOCK_MARKER_BYTES if isinstance(text, bytes) else _BLOCK_MARKERS
    return any(marker in text for marker in markers)


def _blocked_response(response: http.RawResponse) -> bool:
    return is_blocked(response.body, response.status, response.headers)


def _header(headers: Any, name: str) -> str | None:
    if not headers:
        return None
    needle = name.lower()
    for key, value in headers.items():
        if key.lower() == needle:
            return str(value).strip()
    return None


def _header_value(headers: Any, name: str) -> str | None:
    value = _header(headers, name)
    return value.lower() if value is not None else None


def no_google_referer() -> bool:
    """Whether search and best-seller requests skip the Google referer."""
    return os.environ.get(_NO_GOOGLE_REFERER_ENV, "1").strip() != "0"


def _lease(prefix: str, country: str | None) -> sessions.Exit | None:
    """A sticky exit no other lease (of any plugin) holds, or ``None``."""
    try:
        return sessions.lease_exit(prefix, country)
    except (ImportError, NotImplementedError, RuntimeError, ValueError):
        return None


def _take_hedge() -> bool:
    budget = _hedges_left.get()
    if budget is None:  # outside a call: one hedge per fetch, no call budget
        return True
    if budget[0] <= 0:
        return False
    budget[0] -= 1
    return True


def _hedges_available() -> bool:
    budget = _hedges_left.get()
    return budget is None or budget[0] > 0


async def _text(response: http.RawResponse) -> str:
    if len(response.body) > _LARGE_BODY:
        return await asyncio.to_thread(response.text)
    return response.text()


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
    google_referer: bool = True,
    stage: str = "page",
    location: LocationSession | None = None,
    allow_redirects: bool = True,
) -> FetchResult | None:
    """Fetch a page and retry blocked responses with fresh proxy exits.

    ``google_referer=False`` sends no referer; a ``Referer`` in ``headers``
    always wins. On the rotating exits a slow attempt is hedged once on a fresh
    sticky exit (at most a few hedges per call). ``location`` pins the request
    to a delivery-location session's exit and cookies; a block there mints a new
    session on a fresh exit instead of retrying the refused IP. The result names
    the session it was fetched on, which is ``None`` once a renewal failed.
    """
    attempts = _MAX_IP_ATTEMPTS if rotate_on_block else 1
    if location is not None:
        attempts = min(attempts, _LOCATION_TRIES)
    request_headers = {**_HEADERS}
    if accept_language:
        request_headers["Accept-Language"] = (
            f"{accept_language},{accept_language.split('-', 1)[0]};q=0.9"
        )
    request_headers.update(headers or {})
    referer = http.GOOGLE if google_referer else None
    referer_label = (
        "page"
        if any(key.lower() == "referer" for key in headers or {})
        else ("google" if google_referer else "none")
    )

    async def send(
        index: int, selected: str | None, jar: dict[str, str], attempt: int
    ) -> http.RawResponse:
        if index == 0:
            return await _request(selected, jar, attempt)
        if not _take_hedge():
            raise _NoHedgeLeftError
        # A hedge never joins the slow attempt's exit (or its slow tunnel). With
        # no free sticky slot it still goes out, on a new gateway connection.
        exit = _lease("amazon", country)
        blocked = True
        try:
            response = await _request(
                exit.proxy_url() if exit is not None else get_geo_proxy_url(country),
                jar,
                attempt,
            )
            blocked = response.blocked
            return response
        finally:
            if exit is not None:
                sessions.release_exit(exit, burned=blocked)

    async def _request(
        selected: str | None, jar: dict[str, str], attempt: int
    ) -> http.RawResponse:
        return await http.request(
            method,
            url,
            plugin="amazon",
            stage=stage,
            proxy=selected,
            headers=request_headers,
            cookies=jar,
            data=data if method == "POST" else None,
            referer=referer,
            timeout=_TIMEOUT,
            allow_redirects="safe" if allow_redirects else False,
            attempt=attempt,
            is_blocked=_blocked_response,
        )

    failed_on: LocationSession | None = None
    for attempt in range(1, attempts + 1):
        if location is not None:
            location = _current_location(location)
        jar = {**(location.cookies if location else {}), **(cookies or {})}
        rotation: sessions.Exit | None = None
        if location is not None:
            selected = location.proxy
        elif proxy is not None:
            selected = proxy
        elif country and attempt > 1:
            # A retry leaves on a sticky IP no other lease (or recent burn) holds.
            rotation = _lease("amazon", country)
            selected = (
                rotation.proxy_url()
                if rotation is not None
                else get_geo_proxy_url(country)
            )
        else:
            selected = get_geo_proxy_url(country)
        started = time.perf_counter()
        usable = False
        try:
            if location is not None:
                async with location.slots:
                    response = await send(0, selected, jar, attempt)
            elif proxy is None and _hedges_available():
                response = await hedged(
                    lambda index, selected=selected, jar=jar, attempt=attempt: send(
                        index, selected, jar, attempt
                    ),
                    after_s=_HEDGE_AFTER_S.get(stage, _DEFAULT_HEDGE_AFTER_S),
                    accept=lambda response: not response.blocked,
                    plugin="amazon",
                    stage=stage,
                )
            else:
                response = await send(0, selected, jar, attempt)
            usable = not response.blocked
        except Exception as exc:
            logger.warning("Amazon request failed for %s: %s", url, exc)
            if proxy is not None:
                return None
            # A failed handshake on a new connection is common (about 1 in 8),
            # so only a second failure in a row replaces a location exit.
            if location is not None:
                if failed_on is location:
                    location = await renew_location_session(location)
                    failed_on = None
                else:
                    failed_on = location
            continue
        finally:
            if rotation is not None:
                sessions.release_exit(rotation, burned=not usable)

        logger.info(
            "[amazon][perf] method=%s status=%s attempt=%s fetch_ms=%.1f "
            "referer=%s url=%s",
            method,
            response.status,
            attempt,
            (time.perf_counter() - started) * 1000,
            referer_label,
            url,
        )
        if rotate_on_block and response.blocked:
            logger.info(
                "Amazon blocked proxy attempt %s/%s for %s", attempt, attempts, url
            )
            if location is not None:
                location = await renew_location_session(location)
            continue
        return FetchResult(
            status=response.status,
            html=await _text(response),
            url=response.url,
            cookies=dict(response.cookies),
            headers=dict(response.headers),
            location=location,
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
    headers: dict[str, str] | None = None,
    stage: str = "page",
    location: LocationSession | None = None,
) -> str | None:
    """Return public page HTML, or ``None`` when no usable response is obtained."""
    result = await fetch_page(
        url,
        cookies=cookies,
        proxy=proxy,
        country=country,
        accept_language=accept_language,
        headers=headers,
        stage=stage,
        location=location,
    )
    return result.html if result is not None and result.status == 200 else None


async def resolve_shortlink(
    url: str, *, country: str | None = None, accept_language: str | None = None
) -> str | None:
    """Follow a shortened Amazon URL's redirects and return its Amazon destination.

    Redirects are followed by hand and stop at the first page the scraper
    supports, so that page is fetched once, by the flow it dispatches to.
    Amazon's own redirectors on the way are followed like any other hop.
    """
    current = url
    for _ in range(_SHORTLINK_HOPS):
        result = await fetch_page(
            current,
            country=country,
            accept_language=accept_language,
            stage="shortlink",
            allow_redirects=False,
        )
        if result is None:
            return None
        location = _header(result.headers, "location")
        if not 300 <= result.status < 400 or not location:
            return result.url if result.status == 200 else None
        target = urljoin(current, location)
        resolved = resolve_url(target)
        if resolved is not None and resolved.kind in _SHORTLINK_TARGETS:
            return target
        current = target
    return None


def _origin(domain: str) -> str:
    return f"https://{domain}"


def _csrf_token(html: str) -> str | None:
    # The home page carries it in a data-a-modal attribute, as escaped JSON.
    text = html_lib.unescape(html) if "&quot;" in html else html
    for pattern in _CSRF_PATTERNS:
        match = pattern.search(text)
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
    location: LocationSession | None = None,
) -> str | None:
    """Fetch the public all-offers panel for one product.

    ``aodAjaxMain`` is a path segment, not a query param. Amazon also serves this
    panel as a JS-only modal for many (especially US) ASINs, so a 404 here is
    expected and the caller falls back to the PDP buy-box winner.
    """
    url = f"{_origin(domain)}/gp/product/ajax/aodAjaxMain/?asin={asin}"
    # The panel is an XHR from the product page, so send it the way a browser does.
    headers = (
        {
            "Referer": f"{_origin(domain)}/dp/{asin}",
            "X-Requested-With": "XMLHttpRequest",
        }
        if os.environ.get(_AOD_XHR_ENV, "1").strip() != "0"
        else None
    )
    return await fetch_html(
        url,
        cookies=cookies,
        proxy=proxy,
        country=country,
        accept_language=accept_language,
        headers=headers,
        stage="aod",
        location=location,
    )


async def fetch_seller_html(
    seller_id: str,
    domain: str,
    *,
    cookies: dict[str, str] | None = None,
    proxy: str | None = None,
    country: str | None = None,
    accept_language: str | None = None,
    location: LocationSession | None = None,
) -> str | None:
    """Fetch a public seller profile."""
    return await fetch_html(
        f"{_origin(domain)}/sp?seller={seller_id}",
        cookies=cookies,
        proxy=proxy,
        country=country,
        accept_language=accept_language,
        stage="seller",
        location=location,
    )


_LOCATION_SESSION_TTL_S = 30 * 60
_location_sessions: dict[tuple[str, str, str | None], LocationSession] = {}
_location_failures: dict[tuple[str, str, str | None], tuple[float, str]] = {}
_location_locks: dict[tuple[str, str, str | None], asyncio.Lock] = {}


def should_localize(route: str, deliverable_routes: list[str] | None) -> bool:
    """Return whether a request route should use delivery-location state."""
    return route.upper() in {value.upper() for value in (deliverable_routes or [])}


def _lease_location_exit(country: str | None) -> sessions.Exit | None:
    """A sticky exit no other lease holds, so the location cookies keep one IP."""
    return _lease("amazonzip", country)


def _location_key(
    domain: str, zip_code: str, country_code: str | None
) -> tuple[str, str, str | None]:
    return (domain, zip_code, country_code)


def _fresh(session: LocationSession) -> bool:
    return time.time() - session.created_at < _LOCATION_SESSION_TTL_S


def _current_location(session: LocationSession) -> LocationSession:
    """The key's live session, so a task that started on a since-renewed one
    does not spend an attempt on the exit Amazon already refused."""
    current = _location_sessions.get(session.key) if session.key else None
    if current is None or current is session or not _fresh(current):
        return session
    return current


async def get_location_session(
    domain: str,
    *,
    zip_code: str,
    country_code: str | None,
    country: str | None = None,
    accept_language: str | None = None,
) -> LocationSession | None:
    """Create or reuse an anonymous delivery-location session.

    A failure is remembered for a few minutes and reported through the call's
    notes, so later zip calls neither repeat the wasted setup nor ignore the zip
    in silence.
    """
    key = _location_key(domain, zip_code, country_code)
    cached = _location_sessions.get(key)
    if cached and _fresh(cached):
        return cached

    lock = _location_locks.setdefault(key, asyncio.Lock())
    async with lock:
        cached = _location_sessions.get(key)
        if cached and _fresh(cached):
            return cached
        if cached is not None:
            # Expired: its sticky exit goes back to the pool every plugin shares.
            del _location_sessions[key]
            if cached.exit is not None:
                sessions.release_exit(cached.exit)
        failed = _location_failures.get(key)
        if failed and time.time() - failed[0] < _LOCATION_FAILURE_TTL_S:
            note(f"zip_code {zip_code} was not applied: {failed[1]}")
            return None
        session, reason = await _mint_location_session(
            key, country=country, accept_language=accept_language
        )
        if session is None:
            _location_failures[key] = (time.time(), reason)
            note(f"zip_code {zip_code} was not applied: {reason}")
            return None
        _location_failures.pop(key, None)
        _location_sessions[key] = session
        return session


async def renew_location_session(
    session: LocationSession,
) -> LocationSession | None:
    """Replace a location session whose exit Amazon refused with one on a new exit.

    Tasks sharing the refused session renew it once: a task that finds the
    session already replaced takes the replacement.
    """
    key = session.key
    if key is None:
        return None
    async with _location_locks.setdefault(key, asyncio.Lock()):
        current = _location_sessions.get(key)
        if current is not session:
            return current
        del _location_sessions[key]
        if session.exit is not None:
            sessions.release_exit(session.exit, burned=True)
        fresh, reason = await _mint_location_session(
            key, country=session.exit.country if session.exit else None
        )
        if fresh is None:
            _location_failures[key] = (time.time(), reason)
            note(f"zip_code {session.zip_code} was not applied: {reason}")
            return None
        _location_sessions[key] = fresh
        return fresh


async def _mint_location_session(
    key: tuple[str, str, str | None],
    *,
    country: str | None,
    accept_language: str | None = None,
) -> tuple[LocationSession | None, str]:
    """Set the delivery location on a fresh sticky exit; a block tries another."""
    domain, zip_code, country_code = key
    reason = "the home page was blocked on every exit tried"
    for _ in range(_LOCATION_TRIES):
        exit = _lease_location_exit(country)
        # Without a free sticky slot the country gateway still keeps the zip
        # requests on the proxy, never on the host's own IP.
        proxy = exit.proxy_url() if exit is not None else get_geo_proxy_url(country)
        keep = False
        try:
            home = await fetch_page(
                f"{_origin(domain)}/?ref_=nav_logo",
                proxy=proxy,
                country=country,
                accept_language=accept_language,
                rotate_on_block=False,
                stage="home",
            )
            if home is None:
                reason = "the home page did not load"
                continue
            if is_blocked(home.html, home.status, home.headers):
                continue
            if home.status != 200:
                reason = f"the home page returned HTTP {home.status}"
                continue
            csrf = await asyncio.to_thread(_csrf_token, home.html)
            if csrf is None:
                logger.warning("Amazon location session did not expose a CSRF token")
                return None, "Amazon's home page had no location token"

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
                stage="location",
            )
            if changed is None or changed.status != 200:
                reason = "Amazon refused the location change"
                continue
            cookies.update(changed.cookies)
            keep = True
            return (
                LocationSession(
                    proxy=proxy,
                    cookies=cookies,
                    country_code=country_code.upper() if country_code else None,
                    zip_code=zip_code,
                    location_text=zip_code,
                    created_at=time.time(),
                    exit=exit,
                    key=key,
                ),
                "",
            )
        finally:
            if exit is not None and not keep:
                sessions.release_exit(exit, burned=True)
    return None, reason
