"""GET TikTok pages and API JSON through a rotate-on-block, sticky-IP proxy session.

Pages and the comment API answer a cold session: a video page server-renders its
rehydration blob and mints ``ttwid`` itself. The Explore API needs ``ttwid`` first,
so it warms on the homepage; a page that comes back without its blob is retried
once on a warmed session. Rotates the residential IP (and its country) on 403 or a
dead exit, backs off on 429, and raises :class:`TikTokAccessBlockedError` only when
every rotated IP refuses access.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import re
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode
from weakref import WeakKeyDictionary

from proprietary.scraping import http, sessions
from proprietary.scraping.concurrency import hedged
from proprietary.scraping.logged_host import logged_host

from ..extraction import comments_from_response, items_from_response
from .errors import TikTokAccessBlockedError
from .proxy import (
    PLUGIN,
    REQUEST_TIMEOUT,
    pace,
    proxy_session,
    report_stage,
    rotate,
)

logger = logging.getLogger(__name__)

# 403 => IP blocked; rotate and re-warm. 429 => rate limited; back off same IP.
_ROTATE_STATUS = 403
_BACKOFF_STATUS = 429
# Each rotation walks to the next country pool (see session/proxy.py). The bare
# worldwide pool never mints ``ttwid`` (proven live 2026-07-17), so warming
# relies on reaching a good country pool — budget enough rotations to try every
# one at least once (>= len(rotation FALLBACK_COUNTRIES)). Rotating is cheap
# (reopen one keep-alive connection + a 1-request warm), so spend liberally.
_MAX_ROTATIONS = 8
_MAX_BACKOFFS = 4
_BACKOFF_BASE_S = 5.0

_HOME_URL = "https://www.tiktok.com/"
_TTWID_COOKIE = "ttwid"
_HEADERS = {"Accept-Language": "en-US,en;q=0.9"}
_BLOB_MARKER = "__UNIVERSAL_DATA_FOR_REHYDRATION__"
# TIKTOK_PAGE_WARMUP=1 warms on the homepage before every page fetch again; by
# default a page is fetched cold and warmed only when its blob is missing.
_PAGE_WARMUP = os.getenv("TIKTOK_PAGE_WARMUP", "0") == "1"

# A page lands in 0.9-1.5 s; a dead exit holds it to the 5 s connect cap before
# the rotation. TIKTOK_PAGE_HEDGE_S=0 turns the second exit off.
_PAGE_HEDGE_S = float(os.getenv("TIKTOK_PAGE_HEDGE_S", "2"))

# The rotation count at which each holder last warmed: a rotation is a new IP.
_warmed_at: WeakKeyDictionary[Any, int] = WeakKeyDictionary()

# fetch_json's answer when the GET itself failed (a 404, an unexpected status, or
# a transport error on every rotation): not a withheld body, so the API callers
# do not spend another rotation on it.
_UNREACHABLE: Any = object()


def _soft_blocked(response: http.RawResponse) -> bool:
    """A refused status, or TikTok's empty 200, for the perf line's ``blocked=``."""
    return http.default_blocked(response) or (
        response.status == 200 and not response.body.strip()
    )


def _withheld(response: http.RawResponse) -> bool:
    """An API's soft block: a refused status, or a 200 that is not JSON."""
    return http.default_blocked(response) or (
        response.status == 200 and not response.body.lstrip().startswith((b"{", b"["))
    )


async def _get_page(
    h: sessions.SessionHolder, url: str, headers: dict[str, str], *, stage: str
) -> http.RawResponse:
    return await h.request(
        "GET",
        url,
        stage=stage,
        headers=headers,
        timeout=REQUEST_TIMEOUT,
        is_blocked=_soft_blocked if stage in ("page", "warm") else _withheld,
    )


async def warm_session(h: sessions.SessionHolder) -> bool:
    """Mint an anonymous ``ttwid`` cookie; ``True`` if the session can now fetch."""
    try:
        page = await _get_page(h, _HOME_URL, _HEADERS, stage="warm")
    except http.TransportError:
        return False
    return _TTWID_COOKIE in page.cookies


def _page_text(page: http.RawResponse | None) -> str | None:
    if page is None:
        return None
    text = page.text()
    return text if text.strip() else None


async def fetch_html(url: str) -> str | None:
    """Return page HTML, or ``None`` on 404 / non-block failure.

    Hedged: a page that has not landed after ``_PAGE_HEDGE_S`` is asked for on a
    second, fresh exit too, and the first page wins.
    """
    if _PAGE_HEDGE_S <= 0:
        return await _fetch_html(url)
    return await hedged(
        lambda _attempt: _fetch_html(url),
        after_s=_PAGE_HEDGE_S,
        accept=lambda html: html is not None,
        plugin=PLUGIN,
        stage="page",
    )


async def _fetch_html(url: str) -> str | None:
    h = sessions.current()
    if h is None:  # a hedge runs unbound, so it opens its own exit
        async with proxy_session():
            return await _fetch_html(url)
    page = await _get_ok(h, url, _HEADERS, stage="page", warm=_PAGE_WARMUP)
    html = _page_text(page)
    if html is not None and _BLOB_MARKER not in html and _warmed_at.get(h) is None:
        # A cold video page carried its blob on every live probe. Without one, ask
        # once more the old way, on a ttwid-warmed session.
        logger.info(
            "[tiktok] %s came back without its blob; warming and retrying",
            logged_host(url),
        )
        html = _page_text(await _get_ok(h, url, _HEADERS, stage="page", warm=True))
    return html


async def fetch_json(
    url: str, *, referer: str | None = None, warm: bool = True, stage: str = "api"
) -> Any | None:
    """Return a TikTok API body as JSON, or ``None`` when it is empty or not JSON.

    Same rotate-on-403 and back-off-on-429 loop as :func:`fetch_html`. ``warm``
    mints ``ttwid`` first, which the Explore API needs and the comment API does
    not. TikTok soft-blocks with an empty 200, so callers treat ``None`` as
    "withheld"; a GET that failed outright returns ``_UNREACHABLE``.
    """
    h = sessions.current()
    if h is None:
        async with proxy_session():
            return await fetch_json(url, referer=referer, warm=warm, stage=stage)
    headers = {**_HEADERS, "Referer": referer} if referer else _HEADERS
    page = await _get_ok(h, url, headers, stage=stage, warm=warm)
    if page is None:
        return _UNREACHABLE
    if not page.body.strip():
        return None
    try:
        return page.json()
    except ValueError:
        return None


async def _get_ok(
    h: sessions.SessionHolder,
    url: str,
    headers: dict[str, str],
    *,
    stage: str,
    warm: bool,
) -> http.RawResponse | None:
    """GET ``url`` on ``h``; the 200 page, or ``None`` on 404 / failure."""
    attempt = 0
    backoffs = 0
    while True:
        seen = h.rotations
        try:
            if warm and _warmed_at.get(h) != seen:
                warmed_ok = await warm_session(h)
                _warmed_at[h] = seen
                if not warmed_ok:
                    if attempt < _MAX_ROTATIONS:
                        attempt += 1
                        await _rotate(h, "no ttwid", seen=seen, stage=stage)
                        continue
                    raise TikTokAccessBlockedError(
                        f"could not warm session after {attempt} IP rotations: {url}"
                    )
            await pace(h)
            page = await _get_page(h, url, headers, stage=stage)
        except http.TransportError as e:
            logger.warning("[tiktok] GET %s failed: %s", logged_host(url), e.kind)
            if attempt < _MAX_ROTATIONS:
                attempt += 1
                await _rotate(h, e.kind, seen=seen, stage=stage)
                continue
            return None
        status = page.status
        if status == 200:
            return page
        if status == 404:
            return None
        if status == _BACKOFF_STATUS and backoffs < _MAX_BACKOFFS:
            backoffs += 1
            delay = _BACKOFF_BASE_S * (2 ** (backoffs - 1))
            logger.warning(
                "[tiktok] 429 on %s; backing off %.1fs", logged_host(url), delay
            )
            await asyncio.sleep(delay + random.uniform(0, 1))
            continue
        if status == _ROTATE_STATUS and attempt < _MAX_ROTATIONS:
            attempt += 1
            await _rotate(h, "status 403", seen=seen, stage=stage)
            continue
        if status == _ROTATE_STATUS:
            raise TikTokAccessBlockedError(
                f"TikTok refused {url} on {attempt} rotated IPs (403)"
            )
        logger.warning("[tiktok] GET %s returned %s", logged_host(url), status)
        return None


async def _rotate(
    h: sessions.SessionHolder, reason: str, *, seen: int, stage: str
) -> None:
    # Reported so a run of dead exits shows progress instead of silence.
    await report_stage(f"{stage}: new exit ({reason})")
    await rotate(h, reason, seen=seen)


async def _rotated_once(
    h: sessions.SessionHolder, stage: str, make_url: Callable[[], str], **kw: Any
) -> Any | None:
    """Ask a withheld API page once more, on the next country's exit.

    A flagged exit answers 200 with an empty or HTML body; a fresh one usually
    answers in about 1.5 s, where the browser fallback costs 10 s or more.
    ``make_url`` is called after the rotation, for params that follow the exit.
    """
    logger.info("[tiktok] %s withheld on this exit; asking the next country", stage)
    await rotate(h, f"{stage} withheld", seen=h.rotations)
    return await fetch_json(make_url(), stage=stage, **kw)


_COMMENT_API = "https://www.tiktok.com/api/comment/list/"
_COMMENT_PAGE = 20
# 100 comments (MAX_ITEMS) is 5 pages; the cap bounds a cursor that never ends.
_COMMENT_MAX_PAGES = 8
_VIDEO_ID_RE = re.compile(r"/(?:video|photo)/(\d+)")


async def fetch_comments_api(video_url: str, target_count: int) -> list[dict[str, Any]]:
    """Raw comment records over the unsigned comment API, deduped by ``cid``.

    The endpoint the video page's own panel calls answers a cold session without
    a signature, so this replaces a whole browser page load (about 126 MB of
    video through the proxy). Returns ``[]`` when TikTok withholds the thread;
    the caller falls back to the browser.
    """
    match = _VIDEO_ID_RE.search(video_url)
    if match is None:
        return []
    if sessions.current() is None:
        async with proxy_session():
            return await fetch_comments_api(video_url, target_count)
    out: list[dict[str, Any]] = []
    seen: set[Any] = set()
    cursor: Any = 0
    for _page in range(_COMMENT_MAX_PAGES):
        params = {
            "aid": "1988",
            "aweme_id": match.group(1),
            "count": str(_COMMENT_PAGE),
            "cursor": str(cursor),
        }
        url = f"{_COMMENT_API}?{urlencode(params)}"
        ask = {"referer": video_url, "warm": False}
        body = await fetch_json(url, stage="comments", **ask)
        if body is None:  # any page: the cursor does not follow the exit
            body = await _rotated_once(
                sessions.current(), "comments", lambda url=url: url, **ask
            )
        if body is _UNREACHABLE:
            body = None
        batch = comments_from_response(body)
        for raw in batch:
            cid = raw.get("cid")
            if cid is not None and cid in seen:
                continue
            seen.add(cid)
            out.append(raw)
        await report_stage(f"{len(out)} comments fetched")
        if len(out) >= target_count or not batch or not body.get("has_more"):
            break
        cursor = body.get("cursor") or len(out)
    return out[:target_count]


_EXPLORE_API = "https://www.tiktok.com/api/explore/item_list/"
_EXPLORE_REFERER = "https://www.tiktok.com/explore"
# The params the Explore page itself sends (minus its signature and device ids).
# Minimal params (aid, categoryType, count) return a different, evergreen feed, so
# this exact shape is pinned by a unit test.
_EXPLORE_PARAMS = {
    "aid": "1988",
    "app_name": "tiktok_web",
    "app_language": "en",
    "browser_language": "en-US",
    "browser_name": "Mozilla",
    "browser_online": "true",
    "browser_platform": "Win32",
    "channel": "tiktok_web",
    "cookie_enabled": "true",
    "device_platform": "web_pc",
    "categoryType": "120",
    "focus_state": "true",
    "is_new_user": "true",
    "is_page_visible": "true",
    "language": "en",
    "os": "windows",
    "screen_width": "1920",
    "screen_height": "1080",
    "user_is_login": "false",
    "video_encoding": "dash",
    "webcast_language": "en",
}
# Bounds a feed that keeps repeating itself; 16 per pull covers MAX_ITEMS.
_EXPLORE_MAX_PULLS = 10


def explore_params(country: str, *, first: bool) -> dict[str, str]:
    """Query params for one Explore pull, shaped like the page's own requests.

    The page opens with a small cached pull (``pullType=1``), then pages with
    ``pullType=2`` uncached pulls of 16.
    """
    return {
        **_EXPLORE_PARAMS,
        "region": (country or "us").upper(),
        "count": "8" if first else "16",
        "pullType": "1" if first else "2",
        "enable_cache": "true" if first else "false",
    }


def _explore_url(h: sessions.SessionHolder, *, first: bool = True) -> str:
    # The region param follows the holder's current exit.
    params = explore_params(h.exit.country or "", first=first)
    return f"{_EXPLORE_API}?{urlencode(params)}"


async def fetch_trending_api(target_count: int) -> list[dict[str, Any]]:
    """Trending itemStructs over the unsigned Explore API, deduped by id.

    The endpoint answers a ``ttwid``-warmed session without a signature (a cold
    one gets an empty body), so this replaces a whole browser page load. Returns
    ``[]`` when TikTok withholds the feed; the caller falls back to the browser.
    """
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    async with proxy_session() as h:
        for pull in range(_EXPLORE_MAX_PULLS):
            first = pull == 0
            body = await fetch_json(
                _explore_url(h, first=first),
                referer=_EXPLORE_REFERER,
                stage="explore",
            )
            if body is None and first:
                body = await _rotated_once(
                    h, "explore", lambda: _explore_url(h), referer=_EXPLORE_REFERER
                )
            if body is _UNREACHABLE:
                body = None
            fresh = 0
            for item in items_from_response(body):
                item_id = item.get("id")
                if item_id is not None and item_id in seen:
                    continue
                if item_id is not None:
                    seen.add(item_id)
                items.append(item)
                fresh += 1
            if len(items) >= target_count or not fresh:
                break
    return items[:target_count]
