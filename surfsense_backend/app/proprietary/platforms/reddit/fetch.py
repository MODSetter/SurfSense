"""Proxy-aware fetch seam for the Reddit scraper (browser-warm, HTTP-fetch).

All network I/O flows through :func:`fetch_json` and always egresses through the
residential proxy (a direct hit would expose and risk-block the server IP).

Reddit shut anonymous ``.json`` (~May 2026) and, crucially, put a JavaScript
challenge in front of minting the anonymous ``loid`` session cookie: a plain
HTTP GET (even Chrome-impersonated) can no longer mint ``loid`` — it just 403s
on the bot wall (confirmed live 2026-07-18, and yt-dlp #16877). So the recipe is
now two-phase on ONE sticky exit IP:

    1. WARM (once per session): open a real patchright-Chromium stealth browser
       (:func:`warm_session`) on a sticky proxy IP, load a public HTML page so
       the JS challenge runs and mints the anonymous cookie jar (incl. ``loid``).
    2. FETCH (many, fast): replay that minted jar through a plain-HTTP,
       Chrome-impersonated ``FetcherSession`` pinned to the SAME sticky IP,
       GETting ``www.reddit.com/<path>/.json?raw_json=1``. The ``.json`` body
       comes back as raw JSON (no browser HTML wrapper) because this phase is
       plain HTTP, keeping the fast/cheap fan-out — browser cost is paid ONCE
       per warm, not per fetch.

``loid`` binds to the exit IP, so both phases share one sticky proxy session id
(see :meth:`_RotatingSession._open`); a 403/blocked IP rotates to a fresh sticky
id + country and re-warms. This module is a port of ``../youtube/innertube.py``'s
rotate-on-block sticky-session pattern (``_RotatingSession`` + ``_current_session``
ContextVar + ``open_proxy_holder``/``bind_proxy_holder``/``proxy_session``), with
the browser warm bolted on and a ``.json``-shaped :func:`fetch_json`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
import uuid
from contextlib import asynccontextmanager, suppress
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

from scrapling.fetchers import AsyncFetcher, AsyncStealthySession, FetcherSession

from app.utils.proxy import get_proxy_url, get_sticky_proxy_url

# Shared cross-country rotation walk (also used by the TikTok sibling). Kept under
# the historical private names this module and its tests reference.
from app.utils.proxy.rotation import (
    country_for_rotation as _country_for_rotation,
)

logger = logging.getLogger(__name__)


class RedditAccessBlockedError(RuntimeError):
    """Raised when every rotated IP is refused anonymous access.

    This is the yt-dlp "account authentication is required" / "your IP is unable
    to access the Reddit API" branch. We are anonymous-only and cannot log in,
    so instead of silently returning nothing we surface it as a clear error
    (mirrors google_maps' ``SignInRequiredError``). The route can turn it into a
    403 later; for now it just fails loudly.
    """


# Per-flow proxy session, set by ``bind_proxy_holder`` around one continuation
# chain. Reusing one keep-alive connection pins a single sticky exit IP so the
# ``loid`` cookie (bound to that IP) stays valid across the warm-up + every
# subsequent ``.json`` fetch. A ContextVar keeps each concurrent fan-out flow on
# its own session/IP without threading a param through every call.
_current_session: ContextVar[_RotatingSession | None] = ContextVar(
    "reddit_proxy_session", default=None
)

# 403 => this IP is blocked; rotate to a fresh one and re-warm. 429 => rate
# limited; back off on the SAME IP (rotating wouldn't help and burns the pool).
# Split out from youtube's combined ``_BLOCK_STATUSES`` because Reddit wants
# different handling per status (spec section 3).
_ROTATE_STATUS = 403
_BACKOFF_STATUS = 429
# Rotating an IP is cheap (close + reopen one keep-alive connection through the
# gateway + a 2-request warm ≈ a few seconds) and each rotation also walks to the
# next country pool, so we spend rotations liberally: neither a dirty IP nor a
# wholly-blocked country pool should fail a job. 8 ≥ len(_FALLBACK_COUNTRIES), so
# a job tries every country at least once before giving up. Worst case (a genuine
# global block) costs _MAX_ROTATIONS bounded warm attempts before
# RedditAccessBlockedError.
# ponytail: 8 caps that worst case at ~30s; raise if every pool gets dirty at
# once, lower if a real global block is wasting time.
_MAX_ROTATIONS = 8
_MAX_BACKOFFS = 4
_BACKOFF_BASE_S = 5.0

# Reddit 429s aggressively (~60-100 req/min/IP). Pace each sticky session so a
# fast IP can't burst past the per-IP threshold. A live probe (12 rapid fetches
# on one sticky IP => 0x429; scripts/_bench_reddit2.py) showed the natural
# ~0.85s request latency already holds a session near ~1 req/s, so the old 1.0s
# floor just ADDED ~0.4s of dead sleep to every fetch. A 0.5s floor is a no-op
# for typical fetches yet still caps a fast IP at ~2 req/s; the 429 backoff below
# is the real safety net if an IP's limit is tighter.
# ponytail: 0.5s is tuned to dataimpulse residential exits. A pool with a
# stricter per-IP cap may need it raised — watch for 429 log spam and bump it.
_MIN_INTERVAL_S = 0.5
_PACE_JITTER_S = 0.25

# curl's default is 30s, so one dead sticky IP stalled a whole run for 30-50s
# (seen live 2026-07-06). A healthy fetch lands in ~1s; cap at 10s so a dead IP
# costs one bounded wait, then the timeout falls into the generic exception
# branch of fetch_json and rotates to a fresh IP — same treatment as a 403.
_REQUEST_TIMEOUT_S = 10.0

_HEADERS = {"Accept-Language": "en-US,en;q=0.9"}

# Age-gate opt-in, sent on every ``.json`` fetch so NSFW listings aren't blanked
# (the caller filters on ``includeNSFW`` downstream). Mirrors the probe.
_OVER18_COOKIES = {"over18": "1"}

# The browser warm loads *a* public HTML page so Reddit's JS challenge runs and
# mints the anonymous jar; any always-public subreddit works. ``r/popular``
# always exists, so it's a safe default regardless of this session's target.
_WARM_HTML_URL = "https://www.reddit.com/r/popular/"
_LOID_COOKIE = "loid"

# The stealth browser warm (cold start + the page's own ``load``) lands in
# ~6-15s once the solve_cloudflare/network_idle dead-waits are dropped (see
# warm_session), so 30s is a generous ceiling that still bounds a dead exit; the
# fast HTTP ``.json`` fetches keep the tight _REQUEST_TIMEOUT_S above.
_WARM_TIMEOUT_MS = 30_000

# Bound concurrent browser warms so a wide fan-out (up to _FANOUT_CONCURRENCY=16
# workers, each warming once) can't spawn 16 Chromiums at once and OOM the box.
# Warms are staggered, not serialized: a freed slot starts the next worker's warm
# while already-warmed workers fetch over plain HTTP.
# ponytail: 4 is tuned for a ~2GB container; raise on a bigger box, lower if warm
# spikes push memory. Ceiling: a burst of >4 cold workers queues behind this.
_WARM_CONCURRENCY = 4
_warm_slots = asyncio.Semaphore(_WARM_CONCURRENCY)


def now_iso() -> str:
    """UTC timestamp in the millisecond ISO shape used by scraper output."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _browser_cookie_jar(page: Any) -> dict[str, str]:
    """Extract a ``{name: value}`` jar from a browser Response (best-effort).

    Scrapling's browser Response exposes cookies as a list of ``{name, value,
    ...}`` dicts (patchright/playwright shape); tolerate a plain ``{name: value}``
    dict too so a shape change or a fake in tests still works.
    """
    cookies = getattr(page, "cookies", None)
    if isinstance(cookies, dict):
        return {str(k): str(v) for k, v in cookies.items()}
    jar: dict[str, str] = {}
    if isinstance(cookies, (list, tuple)):
        for item in cookies:
            if isinstance(item, dict) and "name" in item and "value" in item:
                jar[str(item["name"])] = str(item["value"])
    return jar


def _parse_json(page: Any) -> Any | None:
    """Parse a scrapling response body into JSON, or ``None``.

    Prefers ``page.json()``; falls back to ``json.loads`` on the raw body when
    the impersonated response hands back text. No ``<pre>`` unwrapping — that was
    a v1 browser artifact and does not apply to plain-HTTP ``.json``.
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


def _build_url(path: str, params: dict[str, Any] | None) -> str:
    """``https://www.reddit.com/<path>/.json?raw_json=1&...`` (always raw_json)."""
    clean = path.strip("/")
    query = {"raw_json": "1", **(params or {})}
    qs = urlencode({k: v for k, v in query.items() if v is not None})
    return f"https://www.reddit.com/{clean}/.json?{qs}"


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
        # Sticky proxy URL shared by the browser warm AND the HTTP fetch session
        # so both egress the SAME exit IP (``loid`` binds to that IP). The minted
        # cookie jar is replayed on every ``.json`` fetch.
        self.proxy: str | None = None
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
            timeout=_REQUEST_TIMEOUT_S,
        )
        self.session = await self._cm.__aenter__()

    async def warm(self) -> bool:
        """Browser-mint the anonymous cookie jar on this session's sticky IP.

        Returns ``True`` and stores the jar (:attr:`cookies`) when ``loid`` was
        minted, else ``False`` (caller rotates the IP and retries).
        """
        jar = await warm_session(self.proxy)
        if jar:
            self.cookies = jar
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
    """Open a warm rotate-on-block session holder (caller owns ``close()``)."""
    holder = _RotatingSession()
    await holder._open()
    return holder


@asynccontextmanager
async def bind_proxy_holder(holder: _RotatingSession):
    """Route this task's fetches through ``holder`` for the enclosed block.

    Does NOT close the holder — enables pooling warm sessions across sequential
    jobs so each job skips the ~2s proxy handshake AND the ``loid`` warm-up.
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


async def warm_session(proxy: str | None) -> dict[str, str] | None:
    """Browser-mint the anonymous cookie jar (incl. ``loid``) on a sticky IP.

    Reddit gates ``loid`` minting behind a JS challenge that a plain-HTTP client
    can't clear, so this spins up patchright-Chromium ONCE per session on the
    given sticky proxy IP, loads a public HTML page so the challenge runs, and
    returns the minted ``{name: value}`` cookie jar. Returns ``None`` when
    ``loid`` wasn't minted (a dirty exit IP), so the caller rotates to a fresh
    sticky IP and retries. Proven live 2026-07-18 (see e2e step 0).

    Takes the sticky ``proxy`` URL (never the fetch session) so the browser
    egresses the SAME exit IP the HTTP ``.json`` fetches will replay the jar on.
    A module-level semaphore bounds concurrent browser launches under fan-out.

    What actually clears Reddit's wall is the stealth browser + ``google_search``
    referer, NOT captcha solving. ``solve_cloudflare`` and ``network_idle`` were
    each ~60s of dead wait per warm (Reddit's wall isn't Cloudflare, so the solver
    hunts a challenge that never appears; and its long-lived connections never go
    network-idle) — dropping both took the warm from ~133s to ~10s with ``loid``
    still minting 3/3 across us/gb/de exits (measured 2026-07-18). A rare miss
    still self-heals: :func:`fetch_json` rotates to a fresh sticky IP and re-warms.
    """
    if proxy is None:
        return None
    async with _warm_slots:
        try:
            async with AsyncStealthySession(
                headless=True,
                google_search=True,
                network_idle=False,
                proxy=proxy,
                timeout=_WARM_TIMEOUT_MS,
            ) as sess:
                page = await sess.fetch(_WARM_HTML_URL)
                jar = _browser_cookie_jar(page)
                return jar if _LOID_COOKIE in jar else None
        except Exception as e:  # a browser crash must not abort the flow
            logger.warning("[reddit] browser warm failed: %s", e)
            return None


async def _get_page(session: Any, url: str, cookies: dict[str, str]) -> Any:
    """GET through the warmed sticky session, or a one-shot proxied fetch.

    ``cookies`` is the browser-minted jar; ``over18`` is merged so NSFW listings
    aren't blanked. The one-shot path (no bound session) has no minted jar and is
    a best-effort fallback only — it can't clear the JS challenge.
    """
    if session is not None:
        return await session.get(
            url, headers=_HEADERS, cookies={**cookies, **_OVER18_COOKIES}
        )
    return await AsyncFetcher.get(
        url,
        headers=_HEADERS,
        cookies=_OVER18_COOKIES,
        proxy=get_proxy_url(),
        stealthy_headers=True,
        timeout=_REQUEST_TIMEOUT_S,
    )


async def fetch_json(path: str, params: dict[str, Any] | None = None) -> Any | None:
    """GET a Reddit ``.json`` endpoint through a ``loid``-warmed HTTP session.

    Returns parsed JSON (dict or list), or ``None`` on 404 / non-block failure.
    Warms the ``loid`` session once per session; rotates the residential IP and
    re-warms on 403; backs off on 429. Raises :class:`RedditAccessBlockedError`
    only when every rotated IP refuses anonymous access (the yt-dlp
    "login required" branch, which we cannot satisfy).
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
            page = await _get_page(session, url, holder.cookies)
            status = page.status

            if status == 200:
                return _parse_json(page)
            if status == 404:
                return None
            if status == _BACKOFF_STATUS and backoffs < _MAX_BACKOFFS:
                backoffs += 1
                delay = _BACKOFF_BASE_S * (2 ** (backoffs - 1))
                logger.warning("[reddit] 429 on %s; backing off %.1fs", path, delay)
                await asyncio.sleep(delay + random.uniform(0, 1))
                continue
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
