"""Proxy-aware fetch seam + InnerTube payload builder for the YouTube scraper.

All network I/O for the scraper flows through :func:`fetch_html` and
:func:`post_innertube`, and always egresses through the residential proxy (never
a direct connection — that would expose and risk-block the server IP). Each job
runs on one keep-alive :mod:`proprietary.scraping.sessions` holder
(:func:`job_session`), so sequential pages share a connection and an exit IP
(roughly halving warm latency vs a fresh rotating IP per request). A block
(403/429 or the ``google.com/sorry`` redirect) rotates the holder at once, and a
request still unanswered after the hedge delay races a second one on a fresh
exit. Parsers and the orchestrator never see which exit served the bytes.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from contextvars import ContextVar
from functools import partial
from typing import Any
from urllib.parse import urljoin, urlsplit

from proprietary.scraping import http, sessions
from proprietary.scraping.concurrency import hedged

logger = logging.getLogger(__name__)

PLUGIN = "youtube"

# One attempt fails fast: connect (TCP, proxy CONNECT, TLS) within 4 s, the whole
# request within 16 s. The rotation loop below is the only retry layer.
_TIMEOUT = (4, 12)

# A probe of 120 sequential requests on one sticky IP saw zero blocks, so we
# stay on one exit for speed and rotate only *reactively*, up to this many times
# per request.
_MAX_ROTATIONS = 3

# Race a second request on a fresh exit once the first is this slow (about 1 in
# 6 new exits took over 5 s). Watch pages are 1-2 MB; InnerTube answers are small.
# The HTML delay sits below the cold p75 (2.7 s), so a cold page fetch often pays
# for a second 1-2 MB download that loses. That proxy bandwidth buys the slow
# tail: a 4 s delay would leave a stuck page about 1.5 s slower.
# YOUTUBE_HEDGE=0 (or SCRAPING_HEDGE=0 for every plugin) turns it off.
_HEDGE_HTML_S = 2.5
_HEDGE_API_S = 1.5
_MAX_HEDGES = 1 if os.getenv("YOUTUBE_HEDGE", "1") != "0" else 0

# YOUTUBE_KEEP_IDLE=1 keeps warm holders between calls (skips 0.5-1.4 s of CONNECT
# and TLS on a warm call); one exit then serves at most _MAX_USES requests, across
# calls, and a block burns it. Off by default, as Google Maps' is: it concentrates
# calls on fewer exits, and its block-rate check ran on only 12 fetches.
_KEEP_IDLE = os.getenv("YOUTUBE_KEEP_IDLE", "0") == "1"
_MAX_USES = 100

_SORRY = "google.com/sorry"

# The tool call's progress hook (server.py sets it): told as each request starts
# and lands, so a long call keeps reporting between items.
on_stage: ContextVar[Callable[[str], Awaitable[None]] | None] = ContextVar(
    "youtube_on_stage", default=None
)

# Consent cookies to dodge the EU consent interstitial that otherwise returns a
# page with no ``ytInitialData``. Mirrors app/routes/youtube_routes.py.
CONSENT_COOKIES = {
    "CONSENT": "PENDING+999",
    "SOCS": "CAISNQgDEitib3FfaWRlbnRpdHlmcm9udGVuZHVpc2VydmVyXzIwMjMwODI5LjA3X3AxGgJlbiADGgYIgOa_pgY",  # pragma: allowlist secret
}
_HTML_HEADERS = {"Accept-Language": "en-US,en;q=0.9"}

# Public InnerTube "WEB" client block. The web API key below is YouTube's
# long-standing public key; ``search``/``next`` may reject a keyless POST where
# ``browse`` accepts it, so the builder can attach both key and visitorData.
INNERTUBE_PUBLIC_API_KEY = (
    "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"  # pragma: allowlist secret
)

INNERTUBE_BROWSE_URL = "https://www.youtube.com/youtubei/v1/browse"
INNERTUBE_SEARCH_URL = "https://www.youtube.com/youtubei/v1/search"
INNERTUBE_NEXT_URL = "https://www.youtube.com/youtubei/v1/next"
INNERTUBE_PLAYER_URL = "https://www.youtube.com/youtubei/v1/player"


def job_session() -> AbstractAsyncContextManager[sessions.SessionHolder]:
    """One job's (or fan-out worker's) holder, bound so the fetch helpers find it."""
    return sessions.bound(PLUGIN, keep_idle=_KEEP_IDLE, max_uses=_MAX_USES)


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


def is_blocked(response: http.RawResponse) -> bool:
    """403/429/444, or the redirect to Google's "unusual traffic" page."""
    return (
        response.status in http.BLOCK_STATUSES
        or _SORRY in (response.location() or "")
        or _SORRY in response.url
    )


async def _send(
    method: str, url: str, hedge_index: int, *, stage: str, **kw: Any
) -> http.RawResponse:
    """One attempt: on the job's holder, or on a fresh exit inside a hedge.

    ``hedged`` unbinds the holder for its hedges, so ``current()`` is ``None``
    there and the hedge pays its own CONNECT on a new IP. A redirect that is not
    the sorry page is followed once, on the same exit.
    """
    h = sessions.current()
    opts = {
        "stage": stage,
        "timeout": _TIMEOUT,
        "allow_redirects": False,
        "is_blocked": is_blocked,
    }

    async def once(method: str, url: str, **more: Any) -> http.RawResponse:
        if h is None:
            proxy = sessions.Exit().proxy_url()
            return await http.request(
                method, url, plugin=PLUGIN, proxy=proxy, **opts, **more
            )
        return await h.request(method, url, **opts, **more)

    seen = h.rotations if h is not None else 0
    r = await once(method, url, **kw)
    location = r.location()
    if not r.blocked and 300 <= r.status < 400 and location:
        more = {k: v for k, v in kw.items() if k != "json"}
        r = await once("GET", urljoin(r.url, location), **more)
    if r.blocked and h is not None and h.rotations == seen:
        # Rotated by the loop below; if a hedge answered instead, the next
        # request on this holder rotates first (and it is never kept idle).
        # A refusal that lands after another task rotated is about the old
        # exit: burning now would throw away the fresh one.
        h.burn(f"status {r.status}")
    return r


async def _fetch(
    method: str,
    url: str,
    *,
    stage: str,
    after_s: float,
    rotations: int = _MAX_ROTATIONS,
    **kw: Any,
) -> http.RawResponse | None:
    """Send with rotate-on-block and hedging; the last answer, or ``None``.

    Tries up to ``rotations + 1`` exits. Returns a blocked response only when
    every exit tried was blocked.
    """
    h = sessions.current()
    hook = on_stage.get()
    last: http.RawResponse | None = None
    for attempt in range(rotations + 1):
        seen = h.rotations if h is not None else 0  # other tasks may share h
        if hook is not None:
            await hook(f"{stage}: attempt {attempt + 1}")
        try:
            last = await hedged(
                partial(_send, method, url, stage=stage, attempt=attempt, **kw),
                after_s=after_s,
                accept=lambda r: not r.blocked,
                max_extra=_MAX_HEDGES,
                plugin=PLUGIN,
                stage=stage,
            )
        except http.TransportError as e:
            logger.warning("[youtube] %s %s failed: %s", stage, url, e.kind)
            if e.kind == "SessionClosed":  # the job ended under us
                return last
            if h is not None:
                await h.rotate(e.kind, seen=seen)
            continue
        if not last.blocked:
            if hook is not None:
                await hook(f"{stage}: fetched")
            return last
        logger.warning("[youtube] %s %s blocked (status %s)", stage, url, last.status)
        if h is not None:
            await h.rotate(f"status {last.status}", seen=seen)
    return last


def _stage(url: str) -> str:
    return urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1] or "html"


async def post_innertube(
    base_url: str,
    payload: dict[str, Any],
    *,
    api_key: str | None = INNERTUBE_PUBLIC_API_KEY,
) -> dict[str, Any] | None:
    """POST an InnerTube payload and return parsed JSON (or ``None`` on failure).

    Always egresses through the proxy (the job's holder, else a one-off exit).
    Never connects directly — a direct hit would expose and risk-block the
    server IP. The public key goes on the first try; a 400 or 403 to the keyed
    call tries once more without it (``browse`` accepts keyless calls).
    """
    stage = _stage(base_url)
    url = f"{base_url}?key={api_key}" if api_key else base_url
    r = await _fetch("POST", url, stage=stage, after_s=_HEDGE_API_S, json=payload)
    if r is not None and api_key and r.status in (400, 403):
        # A 403 is also a block, so the keyed call has already swept every
        # rotation: one keyless exit tells a refused key from a blocked IP.
        r = await _fetch(
            "POST",
            base_url,
            stage=stage,
            after_s=_HEDGE_API_S,
            rotations=_MAX_ROTATIONS if r.status == 400 else 0,
            json=payload,
        )
    if r is None or r.status != 200:
        logger.warning(
            "InnerTube POST %s returned %s", base_url, r.status if r else "nothing"
        )
        return None
    try:
        return r.json()
    except ValueError as e:
        logger.warning("InnerTube POST %s: not JSON (%s)", base_url, e)
        return None


async def fetch_html(
    url: str, *, cookies: dict[str, str] | None = None, stage: str = "html"
) -> str | None:
    """GET a YouTube page and return raw HTML (or ``None`` on failure).

    Fetches through the proxy (the job's holder, else a one-off exit). Sets
    consent cookies by default so EU-egress fetches don't hit the consent wall
    and return a page without ``ytInitialData``. No browser fallback: YouTube's
    blocks are per IP, so a fresh exit is the cure, at a fraction of the cost.
    """
    r = await _fetch(
        "GET",
        url,
        stage=stage,
        after_s=_HEDGE_HTML_S,
        headers=_HTML_HEADERS,
        cookies={**CONSENT_COOKIES, **(cookies or {})},
    )
    if r is None or r.status != 200:
        logger.warning("HTML GET %s returned %s", url, r.status if r else "nothing")
        return None
    return r.text()
