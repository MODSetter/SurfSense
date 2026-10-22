"""Proxy-aware fetch seam for the Reddit scraper: logged-out HTML pages over plain HTTP.

All network I/O flows through :func:`fetch_page` and always egresses through the
residential proxy (a direct hit would expose and risk-block the server IP).

Reddit closed logged-out ``.json`` (2026-10-13) but still serves the HTML its own
site renders for a logged-out visitor. Each sticky exit first asks for one page,
which sets the anonymous ``loid`` jar, and every later page on that exit,
replaying the jar, is served (measured 2026-10-22 on six countries; a browser is
no longer needed). A challenge or a 403 rotates to a fresh sticky id and country.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import time
import uuid
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from contextvars import ContextVar
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from scrapling.fetchers import AsyncFetcher, FetcherSession

from proprietary.scraping.http import FAIL_FAST
from proprietary.scraping.proxy import get_proxy_url, get_sticky_proxy_url

# Shared cross-country rotation walk (also used by the TikTok sibling). Kept under
# the historical private names this module and its tests reference.
from proprietary.scraping.proxy.rotation import (
    country_for_rotation as _country_for_rotation,
)

logger = logging.getLogger(__name__)


class RedditAccessBlockedError(RuntimeError):
    """Raised when every rotated IP is refused anonymous access.

    We are anonymous-only and cannot log in, so instead of silently returning
    nothing we surface it as a clear error (mirrors google_maps'
    ``SignInRequiredError``); the tool turns it into its error.
    """


# Per-flow proxy session, set by ``bind_proxy_holder`` around one continuation
# chain. Reusing one keep-alive connection pins a single sticky exit IP so the
# ``loid`` cookie (bound to that IP) stays valid across the warm-up + every
# subsequent page. A ContextVar keeps each concurrent fan-out flow on its own
# session/IP without threading a param through every call.
_current_session: ContextVar[_RotatingSession | None] = ContextVar(
    "reddit_proxy_session", default=None
)

# The calling tool's progress reporter (server.py sets it per call): each warm
# and fetch is a stage, so a call spent rotating exits is not a silent stream.
on_stage: ContextVar[Callable[[str], Awaitable[None]] | None] = ContextVar(
    "reddit_on_stage", default=None
)


async def _stage(message: str) -> None:
    report = on_stage.get()
    if report is not None:
        await report(message)


# 403 => this IP is blocked; rotate to a fresh one and re-warm. 429 => rate
# limited; back off on the SAME IP (rotating wouldn't help and burns the pool).
_ROTATE_STATUS = 403
_BACKOFF_STATUS = 429
# Rotating is cheap (one new keep-alive connection plus a one-request warm) and
# each rotation walks to the next country pool, so we spend rotations liberally.
# 8 ≥ len(_FALLBACK_COUNTRIES), so a job tries every country at least once.
_MAX_ROTATIONS = 8
_MAX_BACKOFFS = 4
_BACKOFF_BASE_S = 5.0

# A burst of rapid page requests on one exit drew 429s (probe 2026-10-22); 2.5s
# apart drew none. The 429 backoff below stays the safety net.
_MIN_INTERVAL_S = 2.0
_PACE_JITTER_S = 0.5

# curl's default is 30s, so one dead sticky IP stalled a whole run for 30-50s
# (seen live 2026-07-06). Pages run 0.3-1MB; 15s bounds a dead exit to one wait
# before the timeout rotates to a fresh IP like a 403.
_REQUEST_TIMEOUT_S = 15.0
# One attempt per request (Scrapling would retry 3x on the same exit); the
# rotation loop in fetch_page is the only retry layer.
_HTTP_OPTIONS = {**FAIL_FAST, "timeout": (5, _REQUEST_TIMEOUT_S)}

_HEADERS = {"Accept-Language": "en-US,en;q=0.9"}
# A POST is the page's own "more comments" partial: the stealth headers' Google
# referer on one is a 403 network-security page (probe 2026-10-22).
_FORM_HEADERS = {
    **_HEADERS,
    "Referer": "https://www.reddit.com/",
    "Origin": "https://www.reddit.com",
}

# Age-gate opt-in, sent on every page so NSFW listings aren't blanked (the
# caller filters on ``includeNSFW`` downstream).
_OVER18_COOKIES = {"over18": "1"}

# Any small logged-out page mints the jar; r/popular always exists.
_WARM_URL = "https://www.reddit.com/svc/shreddit/community-more-posts/new/?name=popular"
_LOID_COOKIE = "loid"

# What Reddit serves instead of the page a warmed exit asked for: a reCAPTCHA
# page or a JavaScript check. Neither is solved; the exit is swapped.
_CHALLENGE_MARKERS = ("prove your humanity", 'namedItem("solution")')

# Reddit closed logged-out ``.json`` (smoke test 2026-10-13) behind a 403 HTML
# page reading "You've been blocked by network security" on every country. One
# dirty exit can serve the same page, so reads count as closed once this many
# countries agree (0 turns the check off).
_CLOSED_MARKER = "blocked by network security"
_CLOSED_QUORUM = int(os.getenv("REDDIT_CLOSED_QUORUM", "2"))
# Sightings older than this no longer count toward the quorum.
_CLOSED_EVIDENCE_S = 600.0
# Once closed, every call fails at once for this long, then one call probes
# again (0 keeps no memory between calls). If Reddit reopens, recovery waits
# up to this long.
_CLOSED_LATCH_S = float(os.getenv("REDDIT_CLOSED_LATCH_S", "1800"))
# How long the probing call has the endpoint to itself before another may try.
_PROBE_LEASE_S = 120.0


class _ClosedLatch:
    """Process-wide memory that Reddit refuses logged-out reads.

    Without it every call paid up to 9 warms to give up.
    """

    def __init__(self) -> None:
        self.sightings: dict[str, float] = {}  # country -> monotonic time seen
        self.until = 0.0  # monotonic deadline; 0 when not latched
        self.probing = False

    def check(self) -> None:
        """Raise at once while latched; once it expires, let one call probe."""
        if not self.until:
            return
        now = time.monotonic()
        if now < self.until:
            raise RedditAccessBlockedError(self._message(now))
        self.probing = True
        self.until = now + _PROBE_LEASE_S

    def saw_wall(self, country: str) -> None:
        """Record the closed page on ``country``; raise once enough agree."""
        if _CLOSED_QUORUM <= 0:
            return
        now = time.monotonic()
        self.sightings = {
            c: t for c, t in self.sightings.items() if now - t < _CLOSED_EVIDENCE_S
        }
        self.sightings[country or "default"] = now
        # A probe needs only its own sighting: the quorum was met before.
        if len(self.sightings) < (1 if self.probing else _CLOSED_QUORUM):
            return
        self.probing = False
        self.until = now + _CLOSED_LATCH_S if _CLOSED_LATCH_S > 0 else 0.0
        raise RedditAccessBlockedError(self._message(now))

    def opened(self) -> None:
        """Reddit served a page: forget it all."""
        self.sightings.clear()
        self.until = 0.0
        self.probing = False

    def _message(self, now: float) -> str:
        where = " and ".join(sorted(self.sightings)) or "every country tried"
        text = (
            "logged-out reads are closed. Reddit answers a freshly warmed "
            "anonymous session with a 403 'blocked by network security' page "
            f"(seen on {where}), so retrying now fails the same way"
        )
        if not self.until:
            return text + "."
        retry_at = datetime.now(UTC) + timedelta(seconds=self.until - now)
        return text + f"; SurfSense checks again after {retry_at:%H:%M} UTC."


_closed = _ClosedLatch()


def now_iso() -> str:
    """UTC timestamp in the millisecond ISO shape used by scraper output."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _page_text(page: Any) -> str:
    """A response's body as text (scrapling hands back bytes or text)."""
    for attr in ("body", "text"):
        val = getattr(page, attr, None)
        if isinstance(val, bytes):
            return val.decode("utf-8", "replace")
        if isinstance(val, str):
            return val
    return ""


def _build_url(path: str, params: dict[str, Any] | None) -> str:
    """``https://www.reddit.com/<path>?<params>``, the path as Reddit spells it.

    A trailing slash is part of a route: ``more-comments`` with one is a 403.
    """
    qs = urlencode({k: v for k, v in (params or {}).items() if v is not None})
    return f"https://www.reddit.com/{path.lstrip('/')}" + (f"?{qs}" if qs else "")


class _RotatingSession:
    """Owns one live ``FetcherSession`` (sticky IP) and can swap it for a fresh one.

    ``rotate()`` closes the current keep-alive connection and opens a new one, so
    the rotating gateway hands out a different residential exit IP — walking to
    the next country pool (see :func:`_country_for_rotation`) so a wholly-blocked
    pool can't fail the flow. Because the ``loid`` cookie binds to the exit IP,
    ``rotate()`` also drops the warmed state — the next fetch re-warms on the new
    IP. Used sequentially within a single flow (never shared across concurrent
    tasks), so no locking is needed. ``session`` is ``None`` only when no proxy
    is configured.
    """

    def __init__(self) -> None:
        self._cm: Any | None = None
        self.session: Any | None = None
        self.rotations = 0
        self.warmed = False
        self.country = ""
        self.proxy: str | None = None
        # The jar Reddit set on the warm, replayed on every page of this exit.
        self.cookies: dict[str, str] = {}
        self._last_at = 0.0

    async def _open(self) -> None:
        self.warmed = False
        self.cookies = {}
        self.country = _country_for_rotation(self.rotations)
        # A fresh vendor session id per (re)open pins a distinct sticky exit IP,
        # so rotating drops the dirty IP AND its dead cookie jar in one step.
        session_id = uuid.uuid4().hex[:12]
        self.proxy = get_sticky_proxy_url(session_id, self.country)
        if self.proxy is None:
            self._cm = self.session = None
            return
        self._cm = FetcherSession(
            proxy=self.proxy,
            stealthy_headers=True,
            impersonate="chrome",
            **_HTTP_OPTIONS,
        )
        self.session = await self._cm.__aenter__()

    async def warm(self) -> bool:
        """Ask for one page so Reddit sets the anonymous jar on this exit.

        Returns ``True`` and stores the jar (:attr:`cookies`) when ``loid`` was
        set, else ``False`` (caller rotates the IP and retries).
        """
        if self.session is None:
            return False
        with suppress(Exception):
            # Sent with no cookie, this draws a reCAPTCHA page and the exit's
            # full pages a JavaScript check after it (probe 2026-10-22).
            page = await self.session.get(
                _WARM_URL, headers=_HEADERS, cookies=_OVER18_COOKIES
            )
            jar = getattr(page, "cookies", None)
            if isinstance(jar, dict) and _LOID_COOKIE in jar:
                self.cookies = {str(k): str(v) for k, v in jar.items()}
                return True
        return False

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
            "[reddit] rotated proxy session (rotation #%d, country=%s)",
            self.rotations,
            self.country,
        )
        return self.session

    async def pace(self) -> None:
        """Sleep to hold this sticky IP under Reddit's per-IP rate threshold."""
        wait = _MIN_INTERVAL_S - (time.monotonic() - self._last_at)
        if wait > 0:
            await asyncio.sleep(wait + random.uniform(0, _PACE_JITTER_S))
        self._last_at = time.monotonic()


async def open_proxy_holder() -> _RotatingSession:
    """Open a rotate-on-block session holder (caller owns ``close()``)."""
    holder = _RotatingSession()
    await holder._open()
    return holder


@asynccontextmanager
async def bind_proxy_holder(holder: _RotatingSession):
    """Route this task's fetches through ``holder`` for the enclosed block.

    Does NOT close the holder — enables pooling warm sessions across sequential
    jobs so each job skips the proxy handshake AND the ``loid`` warm-up.
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


async def _get_page(
    session: Any, url: str, cookies: dict[str, str], form: dict[str, str] | None
) -> Any:
    """GET (or POST ``form``) through the warmed sticky session, or one-shot.

    The one-shot path (no bound session) has no jar and is a best-effort
    fallback only.
    """
    jar = {**cookies, **_OVER18_COOKIES}
    if session is not None:
        if form is not None:
            return await session.post(
                url, data=form, headers=_FORM_HEADERS, cookies=jar
            )
        return await session.get(url, headers=_HEADERS, cookies=jar)
    if form is not None:
        return await AsyncFetcher.post(
            url,
            data=form,
            headers=_FORM_HEADERS,
            cookies=_OVER18_COOKIES,
            proxy=get_proxy_url(),
            stealthy_headers=True,
            **_HTTP_OPTIONS,
        )
    return await AsyncFetcher.get(
        url,
        headers=_HEADERS,
        cookies=_OVER18_COOKIES,
        proxy=get_proxy_url(),
        stealthy_headers=True,
        **_HTTP_OPTIONS,
    )


def _is_challenge(text: str) -> bool:
    return any(
        marker in text or marker in text.lower() for marker in _CHALLENGE_MARKERS
    )


async def fetch_page(
    path: str,
    params: dict[str, Any] | None = None,
    *,
    form: dict[str, str] | None = None,
) -> str | None:
    """GET a logged-out Reddit page through a ``loid``-warmed HTTP session.

    ``form`` POSTs it instead, as the page's own "more comments" partial does.

    Returns the page's HTML, or ``None`` on 404 / non-block failure. Warms once
    per exit; rotates the residential IP and re-warms on 403 or a challenge page;
    backs off on 429. Raises :class:`RedditAccessBlockedError` when every rotated
    IP refuses, and at once when warmed sessions in ``_CLOSED_QUORUM`` countries
    get the closed page, or while that is latched.
    """
    _closed.check()
    holder = _current_session.get()
    if holder is None:
        # No bound session (e.g. a direct call outside fan_out): open a
        # short-lived warmed session for this one fetch, then tear it down.
        async with proxy_session() as holder:
            return await _fetch_on(holder, path, params, form)
    return await _fetch_on(holder, path, params, form)


async def _fetch_on(
    holder: _RotatingSession,
    path: str,
    params: dict[str, Any] | None,
    form: dict[str, str] | None,
) -> str | None:
    """:func:`fetch_page`'s warm/rotate/backoff loop on one bound holder."""
    url = _build_url(path, params)
    attempt = 0
    backoffs = 0
    while True:
        session = holder.session
        try:
            if session is not None and not holder.warmed:
                country = getattr(holder, "country", "") or "any country"
                await _stage(f"warming an anonymous session ({country})")
                warmed_ok = await holder.warm()
                holder.warmed = True  # attempted; don't re-warm this IP
                if not warmed_ok:
                    if attempt < _MAX_ROTATIONS:
                        attempt += 1
                        await holder.rotate()
                        continue
                    raise RedditAccessBlockedError(
                        f"could not mint loid after {attempt} IP rotations for {path}"
                    )

            await holder.pace()
            await _stage(f"fetching {path}")
            page = await _get_page(session, url, holder.cookies, form)
            status = page.status
            text = _page_text(page)

            if status == 200 and _is_challenge(text):
                logger.info("[reddit] challenge page on %s; rotating", path)
                if attempt < _MAX_ROTATIONS:
                    attempt += 1
                    await holder.rotate()
                    continue
                raise RedditAccessBlockedError(
                    f"Reddit challenged {path} on {attempt} rotated IPs"
                )
            if status in (200, 404):
                _closed.opened()
            if status == 200:
                return text
            if status == 404:
                return None
            if status == _BACKOFF_STATUS and backoffs < _MAX_BACKOFFS:
                backoffs += 1
                delay = _BACKOFF_BASE_S * (2 ** (backoffs - 1))
                logger.warning("[reddit] 429 on %s; backing off %.1fs", path, delay)
                await asyncio.sleep(delay + random.uniform(0, 1))
                continue
            if (
                status == _ROTATE_STATUS
                and holder.cookies
                and _CLOSED_MARKER in text.lower()
            ):
                # Only after a warm: a cold request can meet the same page on
                # the bot wall that the warm exists to clear.
                _closed.saw_wall(getattr(holder, "country", ""))
            if status == _ROTATE_STATUS and attempt < _MAX_ROTATIONS:
                attempt += 1
                await holder.rotate()
                continue
            if status == _ROTATE_STATUS:
                raise RedditAccessBlockedError(
                    f"Reddit refused {path} on {attempt} rotated IPs (403)"
                )
            logger.warning("[reddit] GET %s returned %s", path, status)
            return None
        except RedditAccessBlockedError:
            raise
        except Exception as e:
            logger.warning("[reddit] GET %s failed: %s", path, e)
            if attempt < _MAX_ROTATIONS:
                attempt += 1
                await holder.rotate()
                continue
            return None
