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

This is a direct port of the Reddit plugin's ``fetch.py`` rotate-on-block sticky-session
pattern (``_RotatingSession`` + ``_current_session`` ContextVar +
``open_proxy_holder``/``bind_proxy_holder``/``proxy_session``), with an
Instagram-specific :func:`warm_session` and header set.

Honest ceiling: anonymous Instagram access is the most hostile of our platforms.
Login walls appear as 401/403 and rotate the exit IP; 429 backs off on the same
IP. The safe ``_FANOUT_CONCURRENCY`` is deliberately low. ponytail: the pacing/rotation
constants are calibrated to residential exits and may need retuning per pool —
watch for 401/403/429 log spam and adjust.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import time
from collections.abc import Callable
from contextlib import asynccontextmanager, suppress
from contextvars import ContextVar
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from scrapling.fetchers import AsyncFetcher, FetcherSession

from proprietary.scraping.http import FAIL_FAST
from proprietary.scraping.proxy import get_proxy_url

logger = logging.getLogger(__name__)


class InstagramAccessBlockedError(RuntimeError):
    """Raised when every rotated IP is refused anonymous access.

    This is the Instagram login-wall branch: after warming and rotating, the
    exit IPs still 401/403. We are anonymous-only and cannot log in, so instead
    of silently returning nothing we surface it as a clear error (mirrors
    reddit's ``RedditAccessBlockedError`` / google_maps' ``SignInRequiredError``).
    The plugin's tools turn it into the tool's error.
    """


class InstagramLoginRequiredError(InstagramAccessBlockedError):
    """The endpoint itself needs a login: no exit IP or fresh session gets through."""


# Per-flow proxy session, set by ``bind_proxy_holder`` around one continuation
# chain. Reusing one keep-alive connection pins a single sticky exit IP so the
# warmed ``csrftoken``/``mid`` cookies (bound to that IP) stay valid across the
# warm-up + every subsequent web-endpoint fetch. A ContextVar keeps each
# concurrent fan-out flow on its own session/IP without threading a param
# through every call.
_current_session: ContextVar[_RotatingSession | None] = ContextVar(
    "instagram_proxy_session", default=None
)

# 401/403 => this IP hit the login wall; rotate to a fresh one and re-warm,
# unless the body says the endpoint needs a login (see _login_required).
# 429 => rate limited; back off on the SAME IP (rotating wouldn't help and burns
# the pool).
_ROTATE_STATUSES = frozenset({401, 403})
_BACKOFF_STATUS = 429
_MAX_ROTATIONS = 3
_MAX_BACKOFFS = 4
_BACKOFF_BASE_S = 5.0

# Instagram 429s hard on bursts. Pace each sticky session so a fast IP can't
# burst past the per-IP threshold. ponytail: 1.5s is tuned to residential exits;
# a pool with a stricter per-IP cap may need it raised — watch for 429 log spam.
_MIN_INTERVAL_S = 1.5
_PACE_JITTER_S = 0.5

# A healthy fetch lands in ~1-2s; cap at 15s so a dead sticky IP costs one
# bounded wait, then the timeout falls into the generic exception branch of
# fetch_json and rotates to a fresh IP — same treatment as a 403. One attempt
# per request (Scrapling would retry 3x on the same exit); the rotation loop in
# _fetch is the only retry layer.
_REQUEST_TIMEOUT_S = 15.0
_HTTP_OPTIONS = {**FAIL_FAST, "timeout": (5, _REQUEST_TIMEOUT_S)}

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
# The same redirect for an exit asking too often: a fresh exit clears it (live,
# 2026-10-22, after ~14 page reads on one exit).
_RATE_LIMIT_FLAG = "is_from_rle"

# Hard login wall: api/v1/users/web_profile_info/ answers every anonymous caller
# 401 {"require_login": true, ...} (smoke test 2026-10-13: 8 residential exits
# and the maintainer's home IP alike). Rotating cost 4 paid sessions and 7-24s
# per target for nothing, so the endpoint fails at once and stays failed for
# this long (0 keeps no memory between calls); then the next call asks again.
_LOGIN_WALL_LATCH_S = float(os.getenv("INSTAGRAM_LOGIN_WALL_LATCH_S", "900"))
# endpoint path -> (monotonic deadline, wall-clock time it was seen)
_login_walls: dict[str, tuple[float, datetime]] = {}


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


def _page_text(page: Any) -> str | None:
    """Best-effort HTML/text body of a scrapling response, or ``None``."""
    for attr in ("text", "body", "content"):
        val = getattr(page, attr, None)
        if callable(val):
            with suppress(Exception):
                val = val()
        if isinstance(val, bytes):
            val = val.decode("utf-8", "replace")
        if isinstance(val, str) and val.strip():
            return val
    return None


def _is_login_redirect(page: Any) -> bool:
    """True if IG redirected this request to the anonymous login wall.

    A soft block: the final URL lands on ``/accounts/login/`` (served 200), so
    the status check never fires. Best-effort — returns ``False`` when the
    response exposes no URL.
    """
    final = getattr(page, "url", None)
    return isinstance(final, str) and _LOGIN_PATH in final


def _login_required(page: Any) -> bool:
    """True when a 401/403 body is Instagram's JSON ``require_login`` answer."""
    data = _parse_json(page)
    return isinstance(data, dict) and data.get("require_login") is True


def _endpoint(path: str) -> str:
    """The latch key: the path without its query, so every username shares it."""
    return path.split("?", 1)[0].strip("/")


def _login_wall_error(
    path: str, status: int | None = None
) -> InstagramLoginRequiredError:
    """The refusal for ``path``, latching it when ``status`` is a fresh answer."""
    key = _endpoint(path)
    now = time.monotonic()
    if status is not None and _LOGIN_WALL_LATCH_S > 0:
        _login_walls[key] = (now + _LOGIN_WALL_LATCH_S, datetime.now(UTC))
    text = f"Instagram requires a login for {key}"
    if status is not None:
        text += f" (HTTP {status} require_login on a fresh anonymous session)"
    if key in _login_walls:
        until, seen = _login_walls[key]
        retry_at = datetime.now(UTC) + timedelta(seconds=until - now)
        text += (
            f"; seen at {seen:%H:%M} UTC, SurfSense asks again after "
            f"{retry_at:%H:%M} UTC"
        )
    return InstagramLoginRequiredError(text)


def _check_login_wall(path: str) -> None:
    """Raise at once while ``path`` is latched behind the login wall."""
    key = _endpoint(path)
    wall = _login_walls.get(key)
    if wall is None:
        return
    if time.monotonic() < wall[0]:
        raise _login_wall_error(path)
    del _login_walls[key]


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
            **_HTTP_OPTIONS,
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
        logger.info("[instagram] rotated proxy session (rotation #%d)", self.rotations)
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
        **_HTTP_OPTIONS,
    )


async def fetch_json(path: str, params: dict[str, Any] | None = None) -> Any | None:
    """GET an Instagram web endpoint through a warmed session; parse JSON.

    Returns parsed JSON (dict or list), or ``None`` on 404 / non-block failure.
    See :func:`_fetch` for the warm/rotate/backoff resilience contract.
    """
    return await _fetch(path, params, _parse_json, warm=True)


async def fetch_html(path: str, params: dict[str, Any] | None = None) -> str | None:
    """GET an Instagram web page through a warmed session; return its HTML text.

    Same warm/rotate/backoff resilience as :func:`fetch_json` (a login-wall
    redirect still raises :class:`InstagramAccessBlockedError`), but hands back
    the raw HTML body for the pages that embed their data in the document
    (``/p/<shortcode>/`` embedded PolarisMedia JSON / og-meta) instead of a JSON
    XHR endpoint.
    """
    # Every logged-out page works as an exit's first request (probe 2026-10-23):
    # the warm's csrftoken is the JSON API's, so a page read does not pay for it.
    return await _fetch(path, params, _page_text, warm=False)


async def _fetch(
    path: str,
    params: dict[str, Any] | None,
    extract: Callable[[Any], Any | None],
    *,
    warm: bool,
) -> Any | None:
    """GET an Instagram web endpoint through a warmed HTTP session.

    Applies ``extract`` to the 200 response (JSON parse or HTML text); returns
    ``None`` on 404 / non-block failure. With ``warm``, mints cookies once per
    session first (only the JSON API needs them); rotates the residential IP
    on 401/403, re-warming when it warms; backs off on 429. Raises
    :class:`InstagramAccessBlockedError` when every rotated IP refuses anonymous
    access, and :class:`InstagramLoginRequiredError` at once on a ``require_login``
    answer or while that endpoint is latched (the login wall, which we cannot
    satisfy).
    """
    _check_login_wall(path)
    holder = _current_session.get()
    if holder is None:
        # No bound session (e.g. a direct call outside fan_out): open a
        # short-lived warmed session for this one fetch, then tear it down.
        async with proxy_session():
            return await _fetch(path, params, extract, warm=warm)

    url = _build_url(path, params)
    attempt = 0
    backoffs = 0
    while True:
        session = holder.session
        try:
            if warm and session is not None and not holder.warmed:
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
            if _is_login_redirect(page) and _RATE_LIMIT_FLAG in str(page.url):
                if attempt < _MAX_ROTATIONS:
                    attempt += 1
                    await holder.rotate()
                    continue
                raise InstagramAccessBlockedError(
                    f"Instagram rate-limited {path} on {attempt} rotated IPs"
                )
            if _is_login_redirect(page):
                raise InstagramAccessBlockedError(
                    f"Instagram login wall on {path} (endpoint requires auth)"
                )
            if status == 200:
                return extract(page)
            if status == 404:
                return None
            if status == _BACKOFF_STATUS and backoffs < _MAX_BACKOFFS:
                backoffs += 1
                delay = _BACKOFF_BASE_S * (2 ** (backoffs - 1))
                logger.warning("[instagram] 429; backing off %.1fs", delay)
                await asyncio.sleep(delay + random.uniform(0, 1))
                continue
            if status in _ROTATE_STATUSES:
                if _login_required(page):
                    raise _login_wall_error(path, status)
                # Bare 401/403: a per-IP block that a fresh exit IP recovers, so
                # rotate and re-warm. (The endpoint-level auth walls are caught
                # above and fail fast without rotating.)
                if attempt < _MAX_ROTATIONS:
                    attempt += 1
                    await holder.rotate()
                    continue
                raise InstagramAccessBlockedError(
                    f"Instagram refused {path} on {attempt} rotated IPs ({status})"
                )
            logger.warning("[instagram] GET returned %s", status)
            return None
        except InstagramAccessBlockedError:
            raise
        except Exception as e:
            logger.warning("[instagram] GET failed: %s", e)
            if attempt < _MAX_ROTATIONS:
                attempt += 1
                await holder.rotate()
                continue
            return None
