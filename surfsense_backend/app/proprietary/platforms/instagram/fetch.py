"""Proxy-aware fetch seam for the Instagram scraper (no browser).

All network I/O flows through :func:`fetch_json` and always egresses through the
residential proxy (a direct hit would expose and risk-block the server IP).

Instagram's public web app exposes anonymous JSON endpoints that a logged-out
browser calls, guarded by the ``X-IG-App-ID`` web app id and a warmed
``csrftoken``/``mid`` cookie pair:

    warm one anonymous session (plain GET to ``www.instagram.com/`` mints
    ``csrftoken``/``mid``), then GET the ``api/v1/*/web_info`` /
    ``web_profile_info`` endpoints through that same Chrome-impersonated,
    sticky-IP session with the ``X-IG-App-ID`` header.

This is a direct port of ``../reddit/fetch.py``'s rotate-on-block sticky-session
pattern (``_RotatingSession`` + ``_current_session`` ContextVar +
``open_proxy_holder``/``bind_proxy_holder``/``proxy_session``), with an
Instagram-specific :func:`warm_session` and header set.

Honest ceiling: anonymous Instagram access is the most hostile of our platforms.
Login walls appear as 401/403 and rotate the exit IP; 429 backs off on the same
IP. Observed per-IP/session limits are documented in ``README.md``; the safe
``_FANOUT_CONCURRENCY`` is deliberately low. ponytail: the pacing/rotation
constants are calibrated to residential exits and may need retuning per pool —
watch for 401/403/429 log spam and adjust.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from contextlib import asynccontextmanager, suppress
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

from scrapling.fetchers import AsyncFetcher, FetcherSession

from app.utils.proxy import get_proxy_url

logger = logging.getLogger(__name__)


class InstagramAccessBlockedError(RuntimeError):
    """Raised when every rotated IP is refused anonymous access.

    This is the Instagram login-wall branch: after warming and rotating, the
    exit IPs still 401/403. We are anonymous-only and cannot log in, so instead
    of silently returning nothing we surface it as a clear error (mirrors
    reddit's ``RedditAccessBlockedError`` / google_maps' ``SignInRequiredError``).
    The executor turns it into a 403 for REST callers.
    """


# Per-flow proxy session, set by ``bind_proxy_holder`` around one continuation
# chain. Reusing one keep-alive connection pins a single sticky exit IP so the
# warmed ``csrftoken``/``mid`` cookies (bound to that IP) stay valid across the
# warm-up + every subsequent web-endpoint fetch. A ContextVar keeps each
# concurrent fan-out flow on its own session/IP without threading a param
# through every call.
_current_session: ContextVar[_RotatingSession | None] = ContextVar(
    "instagram_proxy_session", default=None
)

# 401/403 => this IP hit the login wall; rotate to a fresh one and re-warm.
# 429 => rate limited; back off on the SAME IP (rotating wouldn't help and burns
# the pool).
_ROTATE_STATUSES = frozenset({401, 403})
_BACKOFF_STATUS = 429
_MAX_ROTATIONS = 3
_MAX_BACKOFFS = 4
_BACKOFF_BASE_S = 5.0

# Endpoints Instagram serves only to logged-in clients (confirmed live). A bare
# 401/403 here is an endpoint auth wall, not a per-IP block, so every rotated IP
# hits the same wall — fail fast instead of burning the pool, exactly like the
# /accounts/login/ redirect branch. Content endpoints (profiles) still rotate.
_AUTH_WALLED_PATHS = ("web/search/topsearch/", "api/v1/tags/web_info/")

# Instagram 429s hard on bursts. Pace each sticky session so a fast IP can't
# burst past the per-IP threshold. ponytail: 1.5s is tuned to residential exits;
# a pool with a stricter per-IP cap may need it raised — watch for 429 log spam.
_MIN_INTERVAL_S = 1.5
_PACE_JITTER_S = 0.5

# A healthy fetch lands in ~1-2s; cap at 15s so a dead sticky IP costs one
# bounded wait, then the timeout falls into the generic exception branch of
# fetch_json and rotates to a fresh IP — same treatment as a 403.
_REQUEST_TIMEOUT_S = 15.0

# The anonymous web app id every logged-out instagram.com XHR carries. Without
# it the api/v1/*/web_info and web_profile_info endpoints 403 outright.
_IG_APP_ID = "936619743392459"
_HEADERS = {
    "Accept-Language": "en-US,en;q=0.9",
    "X-IG-App-ID": _IG_APP_ID,
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.instagram.com/",
}

# A plain GET to the home page mints the anonymous csrftoken/mid cookie pair.
_WARM_URL = "https://www.instagram.com/"
_BASE = "https://www.instagram.com"
_CSRF_COOKIE = "csrftoken"

# Soft login wall: instead of a 401/403, IG answers an api/v1/* request with a
# 302 to /accounts/login/ that the impersonated client follows to a 200 login
# page. The status is 200 but the body is login HTML, so this evades the
# status-code rotate check — detect it via the response's final URL and treat
# it exactly like a 403.
_LOGIN_PATH = "/accounts/login"


def now_iso() -> str:
    """UTC timestamp in the millisecond ISO shape used by scraper output."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _response_cookie_names(page: Any) -> set[str]:
    """Cookie names set by a response (best-effort across scrapling shapes)."""
    cookies = getattr(page, "cookies", None)
    if isinstance(cookies, dict):
        return set(cookies.keys())
    return set()


def _parse_json(page: Any) -> Any | None:
    """Parse a scrapling response body into JSON, or ``None``.

    Prefers ``page.json()``; falls back to ``json.loads`` on the raw body when
    the impersonated response hands back text.
    """
    fn = getattr(page, "json", None)
    if callable(fn):
        with suppress(Exception):
            return fn()
    for attr in ("body", "text"):
        val = getattr(page, attr, None)
        if isinstance(val, bytes):
            val = val.decode("utf-8", "replace")
        if isinstance(val, str) and val.strip():
            with suppress(Exception):
                return json.loads(val)
            return None
    return None


def _is_login_redirect(page: Any) -> bool:
    """True if IG redirected this request to the anonymous login wall.

    A soft block: the final URL lands on ``/accounts/login/`` (served 200), so
    the status check never fires. Best-effort — returns ``False`` when the
    response exposes no URL.
    """
    final = getattr(page, "url", None)
    return isinstance(final, str) and _LOGIN_PATH in final


def _build_url(path: str, params: dict[str, Any] | None) -> str:
    """Absolute URL for an instagram.com path (accepts already-absolute URLs)."""
    base = path if path.startswith("http") else f"{_BASE}/{path.strip('/')}/"
    if not params:
        return base
    qs = urlencode({k: v for k, v in params.items() if v is not None})
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}{qs}" if qs else base


class _RotatingSession:
    """Owns one live ``FetcherSession`` (sticky IP) and can swap it for a fresh one.

    ``rotate()`` closes the current keep-alive connection and opens a new one, so
    the rotating gateway hands out a different residential exit IP. Because the
    warmed cookies bind to the exit IP, ``rotate()`` also drops the warmed state
    — the next fetch re-warms on the new IP. Used sequentially within a single
    flow (never shared across concurrent tasks), so no locking is needed.
    ``session`` is ``None`` only when no proxy is configured.
    """

    def __init__(self) -> None:
        self._cm: Any | None = None
        self.session: Any | None = None
        self.rotations = 0
        self.warmed = False
        self._last_at = 0.0

    async def _open(self) -> None:
        proxy = get_proxy_url()
        self.warmed = False
        if proxy is None:
            self._cm = self.session = None
            return
        self._cm = FetcherSession(
            proxy=proxy,
            stealthy_headers=True,
            impersonate="chrome",
            timeout=_REQUEST_TIMEOUT_S,
        )
        self.session = await self._cm.__aenter__()

    async def close(self) -> None:
        if self._cm is not None:
            with suppress(Exception):  # best-effort teardown
                await self._cm.__aexit__(None, None, None)
        self._cm = self.session = None

    async def rotate(self) -> Any | None:
        """Drop the current IP and connect through a fresh one. Returns new session."""
        await self.close()
        self.rotations += 1
        await self._open()
        logger.info(
            "[instagram] rotated proxy session (rotation #%d)", self.rotations
        )
        return self.session

    async def pace(self) -> None:
        """Sleep to hold this sticky IP under Instagram's per-IP rate threshold."""
        wait = _MIN_INTERVAL_S - (time.monotonic() - self._last_at)
        if wait > 0:
            await asyncio.sleep(wait + random.uniform(0, _PACE_JITTER_S))
        self._last_at = time.monotonic()


async def open_proxy_holder() -> _RotatingSession:
    """Open a warm rotate-on-block session holder (caller owns ``close()``)."""
    holder = _RotatingSession()
    await holder._open()
    return holder


@asynccontextmanager
async def bind_proxy_holder(holder: _RotatingSession):
    """Route this task's fetches through ``holder`` for the enclosed block.

    Does NOT close the holder — enables pooling warm sessions across sequential
    jobs so each job skips the proxy handshake AND the cookie warm-up.
    """
    token = _current_session.set(holder)
    try:
        yield holder
    finally:
        _current_session.reset(token)


@asynccontextmanager
async def proxy_session():
    """Open one reused, rotate-on-block proxy session for a continuation chain."""
    holder = await open_proxy_holder()
    try:
        async with bind_proxy_holder(holder):
            yield holder
    finally:
        await holder.close()


async def warm_session(session: Any) -> bool:
    """Mint anonymous ``csrftoken``/``mid`` cookies on a freshly opened session.

    Returns ``True`` when a ``csrftoken`` was issued (the session can now reach
    the web endpoints), else ``False`` (caller rotates the IP and retries).

    Takes an already-open ``session`` (never constructs one) so tests can drive
    warm/rotate deterministically with a fake session, exactly like the reddit
    sibling's fetch-resilience tests.
    """
    seen: set[str] = set()
    with suppress(Exception):
        page = await session.get(_WARM_URL, headers=_HEADERS)
        seen |= _response_cookie_names(page)
    return _CSRF_COOKIE in seen


async def _get_page(session: Any, url: str) -> Any:
    """GET through the warmed sticky session, or a one-shot proxied fetch."""
    if session is not None:
        return await session.get(url, headers=_HEADERS)
    return await AsyncFetcher.get(
        url,
        headers=_HEADERS,
        proxy=get_proxy_url(),
        stealthy_headers=True,
        timeout=_REQUEST_TIMEOUT_S,
    )


async def resolve_redirect(url: str) -> str | None:
    """Follow a ``share/`` short URL to its canonical target, or ``None``.

    ``share/`` links redirect to the real post/profile URL; the resolver records
    the original as ``redirectedFromUrl``. Best-effort: returns the final URL
    when the session exposes it, else ``None``.
    """
    holder = _current_session.get()
    if holder is None:
        async with proxy_session():
            return await resolve_redirect(url)
    with suppress(Exception):
        page = await _get_page(holder.session, url)
        final = getattr(page, "url", None)
        if isinstance(final, str) and final and final != url:
            return final
    return None


async def fetch_json(path: str, params: dict[str, Any] | None = None) -> Any | None:
    """GET an Instagram web endpoint through a warmed HTTP session.

    Returns parsed JSON (dict or list), or ``None`` on 404 / non-block failure.
    Warms cookies once per session; rotates the residential IP and re-warms on
    401/403; backs off on 429. Raises :class:`InstagramAccessBlockedError` only
    when every rotated IP refuses anonymous access (the login-wall branch, which
    we cannot satisfy).
    """
    holder = _current_session.get()
    if holder is None:
        # No bound session (e.g. a direct call outside fan_out): open a
        # short-lived warmed session for this one fetch, then tear it down.
        async with proxy_session():
            return await fetch_json(path, params)

    url = _build_url(path, params)
    attempt = 0
    backoffs = 0
    while True:
        session = holder.session
        try:
            if session is not None and not holder.warmed:
                warmed_ok = await warm_session(session)
                holder.warmed = True  # attempted; don't re-warm this IP
                if not warmed_ok:
                    if attempt < _MAX_ROTATIONS:
                        attempt += 1
                        await holder.rotate()
                        continue
                    raise InstagramAccessBlockedError(
                        f"could not warm session after {attempt} IP rotations for {path}"
                    )

            await holder.pace()
            page = await _get_page(session, url)
            status = page.status

            # Endpoint-level login wall (302 -> /accounts/login/, served as 200
            # login HTML): fail fast, do NOT rotate. Unlike the per-IP 401/403
            # below — which recovers on a fresh exit IP, so it still rotates —
            # every rotated IP hits this same wall (observed live), so rotating
            # only burns the pool and re-warms for an unwinnable block. Raising
            # (vs returning None) keeps a blocked target distinguishable from an
            # empty one; fan_out swallows it per-target for partial results.
            if _is_login_redirect(page):
                raise InstagramAccessBlockedError(
                    f"Instagram login wall on {path} (endpoint requires auth)"
                )
            if status == 200:
                return _parse_json(page)
            if status == 404:
                return None
            if status == _BACKOFF_STATUS and backoffs < _MAX_BACKOFFS:
                backoffs += 1
                delay = _BACKOFF_BASE_S * (2 ** (backoffs - 1))
                logger.warning(
                    "[instagram] 429 on %s; backing off %.1fs", path, delay
                )
                await asyncio.sleep(delay + random.uniform(0, 1))
                continue
            if status in _ROTATE_STATUSES:
                # Bare 401/403 on a login-gated endpoint: rotating never clears an
                # endpoint auth wall, so fail fast (mirrors the login-redirect
                # branch above). Other endpoints rotate — a per-IP 401 recovers.
                if any(p in path for p in _AUTH_WALLED_PATHS):
                    raise InstagramAccessBlockedError(
                        f"Instagram login wall on {path} (endpoint requires auth)"
                    )
                if attempt < _MAX_ROTATIONS:
                    attempt += 1
                    await holder.rotate()
                    continue
                raise InstagramAccessBlockedError(
                    f"Instagram refused {path} on {attempt} rotated IPs ({status})"
                )
            logger.warning("[instagram] GET %s returned %s", path, status)
            return None
        except InstagramAccessBlockedError:
            raise
        except Exception as e:
            logger.warning("[instagram] GET %s failed: %s", path, e)
            if attempt < _MAX_ROTATIONS:
                attempt += 1
                await holder.rotate()
                continue
            return None
