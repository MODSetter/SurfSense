"""Proxy-aware fetch seam for the Reddit scraper (no browser).

All network I/O flows through :func:`fetch_json` and always egresses through the
residential proxy (a direct hit would expose and risk-block the server IP).

Reddit deprecated *cold* unauthenticated ``.json`` (a bare anonymous GET now
403s). The maintained anonymous recipe (proven live 2026-07-04, see
``scripts/e2e_reddit_scraper.py`` step 0) is:

    warm one anonymous session cookie (``loid``) with a plain GET to
    ``old.reddit.com`` (``www.reddit.com/svc/shreddit/<slug>`` fallback), then
    GET ``www.reddit.com/<path>/.json?raw_json=1`` through that same
    Chrome-impersonated, sticky-IP session. Which warm URL mints ``loid`` is
    exit-IP dependent, so the order is a tiebreak — see :func:`warm_session`.

``loid`` is Reddit's equivalent of Google Maps' ``NID`` session cookie: an
anonymous, logged-out id that unlocks the public API — no account, no browser.
This module is a direct port of ``../youtube/innertube.py``'s rotate-on-block
sticky-session pattern (``_RotatingSession`` + ``_current_session`` ContextVar +
``open_proxy_holder``/``bind_proxy_holder``/``proxy_session``), with a
Reddit-specific :func:`warm_session` bolted on and a ``.json``-shaped
:func:`fetch_json` instead of an InnerTube POST.
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
_MAX_ROTATIONS = 3
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

_HEADERS = {"Accept-Language": "en-US,en;q=0.9"}

# Age-gate opt-in, sent on every ``.json`` fetch so NSFW listings aren't blanked
# (the caller filters on ``includeNSFW`` downstream). Mirrors the probe.
_OVER18_COOKIES = {"over18": "1"}

# ``svc/shreddit`` needs *a* path to render; any always-public subreddit mints
# ``loid`` just the same. ``r/popular`` always exists, so it's a safe default
# regardless of which target this session ends up serving.
_WARM_SLUG = "r/popular"
_SHREDDIT_URL = (
    "https://www.reddit.com/svc/shreddit/{slug}"
    "?render-mode=partial&seeker-session=false"
)
_OLD_REDDIT_URL = "https://old.reddit.com/"
_LOID_COOKIE = "loid"


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
    the rotating gateway hands out a different residential exit IP. Because the
    ``loid`` cookie binds to the exit IP, ``rotate()`` also drops the warmed
    state — the next fetch re-warms on the new IP. Used sequentially within a
    single flow (never shared across concurrent tasks), so no locking is needed.
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
            proxy=proxy, stealthy_headers=True, impersonate="chrome"
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
        logger.info("[reddit] rotated proxy session (rotation #%d)", self.rotations)
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


async def warm_session(session: Any, *, slug: str = _WARM_SLUG) -> bool:
    """Mint an anonymous ``loid`` cookie on a freshly opened session.

    Returns ``True`` when a ``loid`` was issued (the session can now reach
    ``.json``), else ``False`` (caller rotates the IP and retries).

    Tries ``old.reddit`` (yt-dlp's primary), then ``svc/shreddit``. WHICH one
    mints is exit-IP dependent and roughly random: live probes 2026-07-04 saw
    both directions across sessions on the rotating residential/custom proxy
    (one IP 403s ``old.reddit`` but mints on ``shreddit``; another does the
    reverse, sometimes with an ``rdt`` bot-interstitial). So the order is a
    tiebreak, not an optimization — a fresh session pays ~one wasted warm 403
    either way. That cost is amortized: ``fan_out`` reuses one warmed session
    per worker across many jobs, so warm-up runs once per worker, not per fetch.
    The fallback is what actually matters — it preserves correctness whichever
    way a given IP leans.

    ponytail: sequential two-source warm burns 1 wasted request on ~half of new
    sessions. A parallel warm (gather both, take whichever mints) removes the
    latency but always spends 2 requests; not worth it while warm-up is
    once-per-worker. Revisit only if session churn (not reuse) dominates.

    Takes an already-open ``session`` (never constructs one) so tests can drive
    warm/rotate deterministically with a fake session, exactly like the youtube
    sibling's fetch-resilience tests.
    """
    seen: set[str] = set()
    with suppress(Exception):
        page = await session.get(_OLD_REDDIT_URL, headers=_HEADERS)
        seen |= _response_cookie_names(page)
    if _LOID_COOKIE in seen:
        return True

    # Fallback: mints loid on exit IPs where old.reddit 403s instead.
    with suppress(Exception):
        page = await session.get(_SHREDDIT_URL.format(slug=slug), headers=_HEADERS)
        seen |= _response_cookie_names(page)
    return _LOID_COOKIE in seen


async def _get_page(session: Any, url: str) -> Any:
    """GET through the warmed sticky session, or a one-shot proxied fetch."""
    if session is not None:
        return await session.get(url, headers=_HEADERS, cookies=_OVER18_COOKIES)
    return await AsyncFetcher.get(
        url,
        headers=_HEADERS,
        cookies=_OVER18_COOKIES,
        proxy=get_proxy_url(),
        stealthy_headers=True,
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
                warmed_ok = await warm_session(session)
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
            page = await _get_page(session, url)
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
