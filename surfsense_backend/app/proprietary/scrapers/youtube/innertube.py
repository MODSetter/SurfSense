"""Proxy-aware fetch seam + InnerTube payload builder for the YouTube scraper.

All network I/O for the scraper flows through :func:`fetch_html` and
:func:`post_innertube`, and always egresses through the residential proxy (never
a direct connection — that would expose and risk-block the server IP). Within a
continuation chain, :func:`proxy_session` opens ONE reused keep-alive session so
sequential pages share a connection and a sticky exit IP (roughly halving warm
latency vs a fresh rotating IP per request). HTML pages fall back to a
``StealthyFetcher`` browser tier for anti-bot walls. Parsers and the orchestrator
never see which tier served the bytes.

The ``AsyncFetcher.post(..., json=...)`` + ``page.json()`` / ``page.html_content``
pattern is already proven in ``app/routes/youtube_routes.py``.
"""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Any

from scrapling.fetchers import AsyncFetcher, FetcherSession

from app.utils.proxy import get_proxy_url

try:  # browser tier is optional (needs patchright browsers installed)
    from scrapling.fetchers import StealthyFetcher
except Exception:  # pragma: no cover - import guard
    StealthyFetcher = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Per-flow proxy session (set by ``proxy_session`` around one continuation
# chain). Reusing one keep-alive connection halves warm latency AND pins a
# single sticky exit IP on the rotating gateway, instead of paying a fresh
# TCP+TLS handshake and drawing a new (often slow) residential node per request.
# A ContextVar keeps each concurrent fan-out flow on its own session/IP without
# threading a param through every parser call.
_current_session: ContextVar[_RotatingSession | None] = ContextVar(
    "yt_proxy_session", default=None
)

# Statuses that mean "this IP is throttled/blocked" -> rotate to a fresh one.
# A probe of 120 sequential requests on one sticky IP saw zero blocks, so we
# stay sticky for speed and rotate only *reactively*, up to this many times per
# request. ponytail upgrade path: also rotate proactively every N requests if a
# future run ever trips these.
_BLOCK_STATUSES = frozenset({403, 429})
_MAX_ROTATIONS = 3


class _RotatingSession:
    """Owns one live ``FetcherSession`` (sticky IP) and can swap it for a fresh one.

    ``rotate()`` closes the current keep-alive connection and opens a new one, so
    the rotating gateway hands out a different residential exit IP. Used
    sequentially within a single flow (never shared across concurrent tasks), so
    no locking is needed. ``session`` is ``None`` only when no proxy is configured.
    """

    def __init__(self) -> None:
        self._cm: Any | None = None
        self.session: Any | None = None
        self.rotations = 0

    async def _open(self) -> None:
        proxy = get_proxy_url()
        if proxy is None:
            self._cm = self.session = None
            return
        self._cm = FetcherSession(
            proxy=proxy, stealthy_headers=True, impersonate="chrome"
        )
        self.session = await self._cm.__aenter__()

    async def close(self) -> None:
        if self._cm is not None:
            try:
                await self._cm.__aexit__(None, None, None)
            except Exception:  # best-effort teardown
                pass
        self._cm = self.session = None

    async def rotate(self) -> Any | None:
        """Drop the current IP and connect through a fresh one. Returns new session."""
        await self.close()
        self.rotations += 1
        await self._open()
        logger.info("[youtube] rotated proxy session (rotation #%d)", self.rotations)
        return self.session


async def open_proxy_holder() -> _RotatingSession:
    """Open a warm rotate-on-block session holder (caller owns ``close()``)."""
    holder = _RotatingSession()
    await holder._open()
    return holder


@asynccontextmanager
async def bind_proxy_holder(holder: _RotatingSession):
    """Route this task's fetches through ``holder`` for the enclosed block.

    Does NOT close the holder — enables pooling warm sessions across sequential
    jobs so each job skips the ~2s proxy TCP+TLS handshake.
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

# Consent cookies to dodge the EU consent interstitial that otherwise returns a
# page with no ``ytInitialData``. Mirrors app/routes/youtube_routes.py.
CONSENT_COOKIES = {
    "CONSENT": "PENDING+999",
    "SOCS": "CAISNQgDEitib3FfaWRlbnRpdHlmcm9udGVuZHVpc2VydmVyXzIwMjMwODI5LjA3X3AxGgJlbiADGgYIgOa_pgY",
}

# Public InnerTube "WEB" client block. The web API key below is YouTube's
# long-standing public key; ``search``/``next`` may reject a keyless POST where
# ``browse`` accepts it, so the builder can attach both key and visitorData.
INNERTUBE_PUBLIC_API_KEY = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"

INNERTUBE_BROWSE_URL = "https://www.youtube.com/youtubei/v1/browse"
INNERTUBE_SEARCH_URL = "https://www.youtube.com/youtubei/v1/search"
INNERTUBE_NEXT_URL = "https://www.youtube.com/youtubei/v1/next"


def build_innertube_payload(
    *,
    continuation_token: str | None = None,
    browse_id: str | None = None,
    search_query: str | None = None,
    search_params: str | None = None,
    visitor_data: str | None = None,
    video_id: str | None = None,
    hl: str | None = None,
) -> dict[str, Any]:
    """Build the standard InnerTube ``context.client`` payload.

    Ported from the Scrapfly reference ``call_youtube_api`` but I/O-free so it is
    unit-testable and reusable across browse/search/next/player endpoints.
    ``hl`` selects the response language: a ``/next`` call with a non-default
    ``hl`` returns the video's creator-localized title/description.
    """
    client: dict[str, Any] = {
        "hl": hl or "en",
        "gl": "US",
        "clientName": "WEB",
        "clientVersion": "2.20241111.07.00",
        "platform": "DESKTOP",
        "userInterfaceTheme": "USER_INTERFACE_THEME_DARK",
    }
    if visitor_data:
        client["visitorData"] = visitor_data

    payload: dict[str, Any] = {
        "context": {
            "client": client,
            "user": {"lockedSafetyMode": False},
            "request": {"useSsl": True},
        }
    }
    if browse_id is not None:
        payload["browseId"] = browse_id
    if video_id is not None:
        payload["videoId"] = video_id
    if search_query is not None:
        payload["query"] = search_query
        if search_params is not None:
            payload["params"] = search_params
    if continuation_token is not None:
        payload["continuation"] = continuation_token
    return payload


async def post_innertube(
    base_url: str,
    payload: dict[str, Any],
    *,
    api_key: str | None = None,
) -> dict[str, Any] | None:
    """POST an InnerTube payload and return parsed JSON (or ``None`` on failure).

    Always egresses through the proxy (a reused per-flow session when one is
    open, else a one-shot ``AsyncFetcher``). Never connects directly — a direct
    hit would expose and risk-block the server IP.
    """
    url = f"{base_url}?key={api_key}" if api_key else base_url
    holder = _current_session.get()
    for attempt in range(_MAX_ROTATIONS + 1):
        session = holder.session if holder else None
        try:
            started = time.perf_counter()
            if session is not None:
                page = await session.post(url, json=payload)
            else:
                page = await AsyncFetcher.post(
                    url, json=payload, proxy=get_proxy_url(), stealthy_headers=True
                )
            fetch_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "[youtube][perf] source=innertube reused=%s url=%s status=%s fetch_ms=%.1f",
                session is not None,
                base_url,
                page.status,
                fetch_ms,
            )
            if page.status == 200:
                return page.json()
            logger.warning("InnerTube POST %s returned %s", base_url, page.status)
            if not (holder and page.status in _BLOCK_STATUSES and attempt < _MAX_ROTATIONS):
                return None
        except Exception as e:
            logger.warning("InnerTube POST %s failed: %s", base_url, e)
            if not (holder and attempt < _MAX_ROTATIONS):
                return None
        await holder.rotate()  # blocked/errored on a proxy session: try a fresh IP
    return None


async def fetch_html(url: str, *, cookies: dict[str, str] | None = None) -> str | None:
    """GET a YouTube page and return raw HTML (or ``None`` on failure).

    Fetches through the proxy (reused per-flow session when open, else a one-shot
    ``AsyncFetcher``); falls back to the ``StealthyFetcher`` browser tier for
    anti-bot walls. Sets consent cookies by default so EU-egress fetches don't
    hit the consent wall and return a page without ``ytInitialData``.
    """
    merged = {**CONSENT_COOKIES, **(cookies or {})}
    headers = {"Accept-Language": "en-US,en;q=0.9"}
    holder = _current_session.get()
    for attempt in range(_MAX_ROTATIONS + 1):
        session = holder.session if holder else None
        try:
            started = time.perf_counter()
            if session is not None:
                page = await session.get(url, headers=headers, cookies=merged)
            else:
                page = await AsyncFetcher.get(
                    url,
                    headers=headers,
                    cookies=merged,
                    proxy=get_proxy_url(),
                    stealthy_headers=True,
                )
            fetch_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "[youtube][perf] source=html reused=%s url=%s status=%s fetch_ms=%.1f",
                session is not None,
                url,
                page.status,
                fetch_ms,
            )
            if page.status == 200:
                return page.html_content
            logger.warning("HTML GET %s returned %s", url, page.status)
            if not (holder and page.status in _BLOCK_STATUSES and attempt < _MAX_ROTATIONS):
                break
        except Exception as e:
            logger.warning("HTML GET %s failed: %s", url, e)
            if not (holder and attempt < _MAX_ROTATIONS):
                break
        await holder.rotate()  # blocked/errored on a proxy session: try a fresh IP
    # All proxy attempts blocked/failed -> last-resort browser tier.
    return await _fetch_html_stealthy(url)


async def _fetch_html_stealthy(url: str) -> str | None:
    """Last-resort browser fetch for anti-bot walls (mirrors the crawler tier).

    ``StealthyFetcher.fetch`` is synchronous, so it runs in a worker thread to
    keep the event loop free. Returns ``None`` when the browser tier is
    unavailable or still blocked.
    """
    if StealthyFetcher is None:
        return None
    try:
        started = time.perf_counter()
        page = await asyncio.to_thread(
            StealthyFetcher.fetch,
            url,
            headless=True,
            network_idle=True,
            solve_cloudflare=True,
            proxy=get_proxy_url(),
        )
        fetch_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "[youtube][perf] source=html tier=stealthy url=%s status=%s fetch_ms=%.1f",
            url,
            page.status,
            fetch_ms,
        )
        if page.status == 200:
            return page.html_content
        logger.warning("HTML GET %s tier=stealthy returned %s", url, page.status)
    except Exception as e:
        logger.warning("HTML GET %s tier=stealthy failed: %s", url, e)
    return None
