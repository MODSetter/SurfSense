"""Browser-driven listing fetch: let TikTok sign its own ``item_list`` XHRs.

Profile/hashtag/search listings need signed requests (``X-Gnarly``) whose
algorithm rev's monthly and reads a browser canvas fingerprint. Rather than port
and chase that signer, we load the page in the shared stealth browser
(patchright-Chromium, :mod:`proprietary.scraping.browser_pool`) and capture the
itemStruct JSON the page's own scripts fetch while scrolling. The browser is the
client, so it signs correctly for whatever version TikTok ships.

The pure response-shape parsing lives in :func:`items_from_response`; this module
is the browser-I/O glue, unit-tested over fake pages.

Needs a residential proxy; datacenter IPs get empty bodies and 429s. TikTok also
withholds the feed (empty 200, or a redirect to /login) from the provider's
unpinned worldwide pool, so :func:`_fetch_with_rotation` walks country-pinned
exits until a draw is non-empty — the same escape the Reddit/ttwid warm path uses
(see :mod:`proprietary.scraping.proxy.rotation`). A draw whose first XHR is slow
is hedged on the next country instead of waited out.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import Counter
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any
from urllib.parse import urlsplit

from proprietary.scraping import browser_pool, settle
from proprietary.scraping.browser_pool import LaunchProfile
from proprietary.scraping.concurrency import hedged
from proprietary.scraping.logged_host import logged_host
from proprietary.scraping.proxy import get_geo_proxy_url
from proprietary.scraping.proxy.rotation import country_for_rotation

from ..extraction import (
    comments_from_response,
    items_from_response,
    users_from_response,
)
from .client import fetch_comments_api, fetch_trending_api
from .proxy import PLUGIN, report_stage
from .stealth import get_stealth_config, location_to_locale_timezone

logger = logging.getLogger(__name__)

ExtractFn = Callable[[Any], list[dict[str, Any]]]


class _Capture:
    """What one browser attempt captured, plus the counters its waits poll."""

    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []
        # Matching XHRs read, empty ones included: a wait ends on any new one.
        self.responses = 0
        # Matching XHRs whose body was empty or not JSON (TikTok's soft error).
        self.empty = 0
        # Why the attempt ended early (geo_block, login, page_error), if it did.
        self.exit_reason = ""
        # When the pool lent this attempt its page (monotonic): the hedge clock
        # starts here, not while the draw queues for a page or a browser launches.
        self.lent_at: float | None = None
        # The draw is over; a hedge waiting on it stops waiting.
        self.done = False
        # A hedge that got its page after page one came and never navigated.
        self.skipped = False


# Drives the page after navigation to trigger/paginate the target XHRs, filling
# ``capture.items`` until it reaches ``target_count`` (or the interaction gives up).
InteractFn = Callable[[Any, _Capture, int], Awaitable[None]]

# XHR paths that carry itemStructs for the three listing kinds.
_ITEM_LIST_MARKERS = (
    "/api/post/item_list",
    "/api/challenge/item_list",
    "/api/search/",
)
# The user-search XHR carries account records (user_list), not itemStructs.
_USER_SEARCH_MARKERS = ("/api/search/user",)
# The Explore feed's trending videos arrive as ordinary itemStructs.
_EXPLORE_MARKERS = ("/api/explore/item_list",)
# The comment feed fires only after the comments panel is opened.
_COMMENT_MARKERS = ("/api/comment/list",)
_COMMENT_ICON_SELECTOR = '[data-e2e="comment-icon"], [data-e2e="browse-comment"]'
# The comment icon renders 5-10 s after DOM-ready on a slow exit (seen live).
_COMMENT_ICON_WAIT_MS = 15000
# A click that lands before the SPA wires the icon up fires nothing, so click
# again while no comment XHR has come (the XHR follows a live click in < 1 s).
_COMMENT_CLICKS = 4
_COMMENT_RECLICK_MS = 2500
_HOME_URL = "https://www.tiktok.com/"
_GOOGLE = "https://www.google.com/"
_MSTOKEN_COOKIE = "msToken"
# Bounded scroll: a dead page can't loop forever, and a live one stops early
# once enough items are captured.
_SCROLL_MAX_ROUNDS = 20
# Event-driven waits poll the capture this often instead of sleeping a fixed time.
_POLL_MS = 100
# Target DOM-ready -> first matching XHR, then one scroll round -> its next XHR.
_FIRST_RESPONSE_MS = 8000
_ROUND_RESPONSE_MS = 4000
# Re-scroll within a round: the feed may render the last page after our scroll.
_RESCROLL_MS = 1000
# User search: TikTok's own "Try again" re-issues the XHR; capped so a real
# no-match query still ends quickly.
_SEARCH_ERROR_TITLE = '[data-e2e="search-error-title"]'
_SEARCH_ERROR_WAIT_MS = 2000
_SEARCH_RETRY_MS = 6000
_SEARCH_MAX_RETRIES = 2
# Warm-up poll for the anonymous msToken cookie (only with TIKTOK_BROWSER_WARMUP=1).
_WARM_POLLS = 8
_WARM_POLL_MS = 500
# Every successful goto seen live took 0.5-4.4 s; the page's default timeout
# bounds DOM-ready (and every other page call) so a dead exit costs 12 s at most.
_PAGE_TIMEOUT_MS = 12000
# Each empty draw retries on a fresh exit country; 1 suits a static IP.
_LISTING_MAX_ATTEMPTS = int(os.getenv("TIKTOK_LISTING_MAX_ATTEMPTS", "3"))
# A draw that has held its page this long with no matching XHR is hedged on the
# next country (one hedge per round). TIKTOK_HEDGE_AFTER_S=0 or SCRAPING_HEDGE=0
# turns hedging off. The perf line's hedge= counts hedges started, including
# those that back out (logged as "hedge skipped"), not pages opened.
_HEDGE_AFTER_S = float(os.getenv("TIKTOK_HEDGE_AFTER_S", "7"))
# Promises an Xvfb display (DISPLAY set), so the profile feed's browser can run
# headful: TikTok serves it empty to headless Chromium.
_HEADED = os.getenv("CRAWL_HEADED_XVFB_ENABLED", "FALSE").upper() == "TRUE"
# TIKTOK_BROWSER_WARMUP=1 restores the homepage msToken warm-up: explore, users,
# hashtag and comments load without it, and profile recovers with one scroll.
_BROWSER_WARMUP = os.getenv("TIKTOK_BROWSER_WARMUP", "0") == "1"
# TIKTOK_BLOCK_MEDIA=0 lets images, fonts and video through again. Blocked, a
# video page pulls 2-6 MB through the paid proxy instead of up to 126 MB.
# Stylesheets stay: the feed's layout drives scroll height and clicks.
_BLOCK_MEDIA = os.getenv("TIKTOK_BLOCK_MEDIA", "1") != "0"
_BLOCKED_RESOURCE_TYPES = frozenset({"image", "media", "font"})
_VIDEO_URL_PATTERNS = ("mime_type=video", "/video/tos/", ".mp4", ".m4s")
# TIKTOK_TRENDING_API=0 sends trending through the browser again.
_TRENDING_API = os.getenv("TIKTOK_TRENDING_API", "1") != "0"
# TIKTOK_COMMENTS_API=0 sends comments through the browser again.
_COMMENTS_API = os.getenv("TIKTOK_COMMENTS_API", "1") != "0"
# Exits TikTok bounced to /notfound or /login, per country, for the logs.
_BAD_EXITS: Counter[str] = Counter()
# A call's cap on comment threads in the browser fallback at once, bound by the
# orchestrator; the API path is not held to it.
BROWSER_SLOTS: ContextVar[asyncio.Semaphore | None] = ContextVar(
    "tiktok_browser_slots", default=None
)


async def _has_mstoken(page: Any) -> bool:
    try:
        cookies = await page.context.cookies()
    except Exception:
        return False
    return any(c.get("name") == _MSTOKEN_COOKIE for c in cookies)


async def _dismiss_login_modal(page: Any) -> None:
    """Close the login modal that blocks scrolling; Escape as fallback.

    Only the modal's own close button, never a generic dialog button (avoids
    clicking "Log in").
    """
    try:
        closed = await page.evaluate(
            """() => {
              const btn = document.querySelector('[data-e2e="modal-close-inner-button"]');
              if (btn) { btn.click(); return true; }
              return false;
            }"""
        )
        if not closed:
            await page.keyboard.press("Escape")
    except Exception:
        pass


async def _wait_for(page: Any, ready: Callable[[], bool], timeout_ms: int) -> bool:
    """Poll ``ready`` every ``_POLL_MS`` (the page's events fire meanwhile)."""
    for _ in range(max(1, timeout_ms // _POLL_MS)):
        if ready():
            return True
        await page.wait_for_timeout(_POLL_MS)
    return ready()


async def _scroll_to_bottom(page: Any) -> bool:
    await _dismiss_login_modal(page)
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    return True


async def _scroll_last_comment(page: Any) -> bool:
    # The panel scrolls, not the page (which would advance the video feed).
    return bool(
        await page.evaluate(
            """() => {
              const items = document.querySelectorAll('[data-e2e="comment-level-1"]');
              if (!items.length) return false;
              items[items.length - 1].scrollIntoView({block: 'end'});
              return true;
            }"""
        )
    )


Nudge = Callable[[Any], Awaitable[bool]]


async def _scroll_round(page: Any, capture: _Capture, nudge: Nudge) -> bool:
    """Nudge the feed until a new matching XHR lands; ``False`` when none does."""
    before = capture.responses
    for step in range(_ROUND_RESPONSE_MS // _POLL_MS):
        if step % (_RESCROLL_MS // _POLL_MS) == 0 and not await nudge(page):
            return False
        await page.wait_for_timeout(_POLL_MS)
        if capture.responses > before:
            return True
    return False


async def _paginate(
    page: Any,
    capture: _Capture,
    target_count: int,
    nudge: Nudge,
    seen: int = 0,
) -> None:
    """Wait for page one, then scroll until enough items or a round brings nothing.

    ``seen`` is the response count before the navigation that page one follows.
    A round that draws a new XHR also re-triggers a cold context's empty first
    ``item_list`` (profile feeds).
    """
    await _wait_for(page, lambda: capture.responses > seen, _FIRST_RESPONSE_MS)
    for _ in range(_SCROLL_MAX_ROUNDS):
        if len(capture.items) >= target_count:
            break
        if not await _scroll_round(page, capture, nudge):
            break


async def _scroll_page(page: Any, capture: _Capture, target_count: int) -> None:
    """Page down a listing feed until enough items are captured or it stops growing.

    Without the old homepage warm-up, a cold context's first ``item_list`` can
    come back empty and the empty feed may not scroll. One reload re-asks with
    the cookies the first load minted, before the caller pays for a new exit.
    """
    await _paginate(page, capture, target_count, _scroll_to_bottom)
    if capture.items or not capture.empty:
        return
    seen = capture.responses
    await page.reload(wait_until="domcontentloaded")
    await _paginate(page, capture, target_count, _scroll_to_bottom, seen)


async def _open_comments(page: Any, capture: _Capture) -> None:
    """Click the comment icon until the first ``/api/comment/list`` XHR fires.

    The icon hydrates a beat after DOM-ready, so we wait for it, then click by JS:
    a normal click timed out on every live run (an overlay intercepts it).
    """
    await page.wait_for_selector(_COMMENT_ICON_SELECTOR, timeout=_COMMENT_ICON_WAIT_MS)
    for _ in range(_COMMENT_CLICKS):
        await page.eval_on_selector(_COMMENT_ICON_SELECTOR, "el => el.click()")
        if await _wait_for(page, lambda: capture.responses > 0, _COMMENT_RECLICK_MS):
            return


async def _scroll_comments(page: Any, capture: _Capture, target_count: int) -> None:
    """Open the comments panel, then scroll its last comment into view to paginate.

    Comment XHRs fire only after the panel is opened, and paging must scroll the
    panel, so we anchor on the last ``comment-level-1`` element. ponytail: naive
    scroll-to-last paging, bounded by ``_SCROLL_MAX_ROUNDS``; upgrade to
    container-height tracking if deep threads under-fetch.
    """
    await _open_comments(page, capture)
    if not capture.responses:
        return  # the panel never opened; nothing to page through
    await _paginate(page, capture, target_count, _scroll_last_comment)


async def _click_search_retry(page: Any) -> bool:
    """Click the button inside TikTok's search-error panel, never a generic one.

    Walks up from the error title to its own container, so a "Log in" button
    elsewhere on the page is never touched.
    """
    try:
        await page.wait_for_selector(_SEARCH_ERROR_TITLE, timeout=_SEARCH_ERROR_WAIT_MS)
    except Exception:
        return False
    return bool(
        await page.evaluate(
            """() => {
              const title = document.querySelector('[data-e2e="search-error-title"]');
              if (!title) return false;
              let box = title.parentElement;
              for (let i = 0; i < 4 && box && !box.querySelector('button'); i++) {
                box = box.parentElement;
              }
              const button = box ? box.querySelector('button') : null;
              if (button) button.click();
              return !!button;
            }"""
        )
    )


async def _search_users(page: Any, capture: _Capture, target_count: int) -> None:
    """Users tab: recover TikTok's soft error in the page before rotating.

    The first ``/api/search/user`` body often comes back empty with a "Something
    went wrong" panel. Its own retry button re-issues the signed XHR in about 1 s,
    where a rotation costs a whole new context and country. A JSON body without
    users is a real no-match and is never retried.
    """
    await _wait_for(page, lambda: capture.responses > 0, _FIRST_RESPONSE_MS)
    for _ in range(_SEARCH_MAX_RETRIES):
        if capture.items or not capture.empty:
            break
        before = capture.responses
        if not await _click_search_retry(page):
            break
        logger.info("[tiktok] user search came back empty; retrying in the page")
        await _wait_for(page, lambda b=before: capture.responses > b, _SEARCH_RETRY_MS)
    if capture.items:
        await _paginate(page, capture, target_count, _scroll_to_bottom)


def _bad_exit_reason(url: str) -> str:
    """``geo_block`` / ``login`` when TikTok bounced this exit, else ``""``."""
    path = urlsplit(url or "").path
    if "/notfound" in path:
        return "geo_block"
    if path == "/login" or path.startswith("/login/"):
        return "login"
    return ""


def _page_url(page: Any) -> str:
    try:
        return page.url
    except Exception:
        return "?"


async def _drive(
    page: Any,
    capture: _Capture,
    url: str,
    target_count: int,
    markers: tuple[str, ...],
    extract: ExtractFn,
    interact: InteractFn,
    *,
    kind: str = "listing",
    referer: str | None = None,
) -> None:
    """Navigate to the target and capture matching XHRs into ``capture``.

    The listener is attached before the target goto so page one fires into it;
    ``interact`` pages the rest. ``markers``/``extract`` select which XHRs to keep
    and how to unwrap them. An exit TikTok bounces to ``/notfound`` (geo-placed
    elsewhere) or ``/login`` ends the attempt at once so the caller rotates.
    """

    async def _on_response(response: Any) -> None:
        response_url = getattr(response, "url", "")
        if not any(marker in response_url for marker in markers):
            return
        try:
            body = await response.json()
        except Exception:
            # An empty 200 (TikTok soft-block) or a body evicted before read.
            capture.empty += 1
            capture.responses += 1
            logger.info(
                "[tiktok] empty or non-JSON %s body from %s",
                kind,
                logged_host(response_url),
            )
            return
        # Counted once the items are in, so a wait that ends on it sees them.
        capture.items.extend(extract(body))
        capture.responses += 1

    async def _warm() -> None:
        if await _has_mstoken(page):
            return
        await settle.goto(page, _HOME_URL, referer=referer)
        for _ in range(_WARM_POLLS):
            await page.wait_for_timeout(_WARM_POLL_MS)
            if await _has_mstoken(page):
                break

    def _bounced() -> bool:
        reason = _bad_exit_reason(_page_url(page))
        if reason:
            capture.exit_reason = reason
        return bool(reason)

    page.on("response", _on_response)
    stage = "goto"
    try:
        if _BROWSER_WARMUP:
            stage = "warm"
            await _warm()
            if _bounced():
                return
        stage = "goto"
        await settle.goto(page, url, wait_until="domcontentloaded", referer=referer)
        if _bounced():
            return
        stage = "interact"
        await interact(page, capture, target_count)
    except Exception as exc:
        capture.exit_reason = capture.exit_reason or (
            "page_error" if stage != "interact" else ""
        )
        logger.warning(
            "[tiktok] %s %s failed (%s) at %s",
            kind,
            stage,
            type(exc).__name__,
            logged_host(_page_url(page)),
        )


def _launch(headless: bool) -> tuple[LaunchProfile, dict[str, Any] | None, str | None]:
    """The shared-pool launch profile, context options and goto referer.

    The same anti-detection levers the per-draw StealthyFetcher took, from the
    crawler's CRAWL_* settings; the locale follows the provider's configured
    region, not the rotation country, so it stays one browser.
    """
    cfg = get_stealth_config()
    locale = timezone_id = None
    if cfg.geoip_match_enabled:
        locale, timezone_id = location_to_locale_timezone(cfg.proxy_location)
    profile = LaunchProfile(
        headless=headless,
        block_webrtc=cfg.block_webrtc,
        hide_canvas=cfg.hide_canvas,
        dns_over_https=cfg.dns_over_https,
        locale=locale,
    )
    options = {"timezone_id": timezone_id} if timezone_id else None
    return profile, options, _GOOGLE if cfg.google_search else None


async def _draw(
    url: str,
    target_count: int,
    markers: tuple[str, ...],
    extract: ExtractFn,
    interact: InteractFn,
    *,
    country: str,
    capture: _Capture,
    headless: bool = True,
    kind: str = "listing",
    abandon: Callable[[], bool] | None = None,
) -> list[dict[str, Any]]:
    """One browser attempt: a fresh context on ``country``'s exit in the shared pool.

    No robots.txt primer and no browser launch or close on the call's path:
    ``settle.goto`` waits for DOM-ready, which TikTok's SPA reaches long before
    the ``load`` event the old fetcher waited for. ``abandon`` is asked once the
    page is lent: a hedge that queued for its page while the first draw's page
    one came gives the page back without navigating.
    """
    profile, options, referer = _launch(headless)

    async def on_loop() -> None:
        async with browser_pool.page(
            PLUGIN,
            profile,
            proxy=get_geo_proxy_url(country),
            disable_resources=_BLOCKED_RESOURCE_TYPES if _BLOCK_MEDIA else False,
            block_url_patterns=_VIDEO_URL_PATTERNS if _BLOCK_MEDIA else (),
            context_options=options,
            timeout_ms=_PAGE_TIMEOUT_MS,
        ) as pooled:
            capture.lent_at = time.monotonic()
            if abandon is not None and abandon():
                capture.skipped = True
                logger.info("[tiktok] %s hedge skipped: page one came", kind)
                return
            await _drive(
                pooled.page,
                capture,
                url,
                target_count,
                markers,
                extract,
                interact,
                kind=kind,
                referer=referer,
            )
            if capture.exit_reason in ("geo_block", "login"):
                pooled.burn(capture.exit_reason)

    try:
        await browser_pool.run(on_loop)
    except Exception as exc:
        # The context could not be built (a wedged browser): an empty draw.
        logger.warning(
            "[tiktok] %s browser attempt failed for %s (%s)",
            kind,
            logged_host(url),
            type(exc).__name__,
        )
        capture.exit_reason = capture.exit_reason or "page_error"
    finally:
        capture.done = True
    return capture.items[:target_count]


async def warm_browser() -> None:
    """Launch the headless browser now, with no page and no proxy.

    User search, the API fallbacks, and every listing without an Xvfb display
    run on it; a headful profile browser still launches on its first call.
    """
    await browser_pool.warm(_launch(headless=True)[0])


def _reason(capture: _Capture) -> str:
    return capture.exit_reason or ("empty_body" if capture.empty else "no_items")


async def _hedge_wait(primary: _Capture) -> str:
    """Wait until ``primary`` has held its page ``_HEDGE_AFTER_S`` with no XHR.

    Returns why not to hedge after all, or ``""`` to hedge. Time queued for a
    page (the plugin and global page caps) or spent launching a browser is not a
    slow exit, and a hedge started then would only queue behind it.
    """
    while True:
        if primary.responses:
            return "page one came"
        if primary.done:
            return "the first draw ended"
        lent_at = primary.lent_at
        if lent_at is not None and time.monotonic() - lent_at >= _HEDGE_AFTER_S:
            return ""
        await asyncio.sleep(_POLL_MS / 1000)


async def _fetch_with_rotation(
    page_url: str,
    target_count: int,
    markers: tuple[str, ...],
    extract: ExtractFn,
    interact: InteractFn,
    *,
    headless: bool = True,
    kind: str = "listing",
) -> list[dict[str, Any]]:
    """Capture matching XHRs, walking exit *countries* until a draw is non-empty.

    TikTok withholds ``item_list``/``comment`` bodies from DataImpulse's unpinned
    worldwide pool (the pool ``PROXY_URL`` uses for SERP health) but serves them on
    country-pinned exits, so each empty draw retries on a fresh country rather than
    the same flagged pool (see :mod:`proprietary.scraping.proxy.rotation`). Non-geo providers
    ignore the country and re-draw their one URL, so this stays a safe no-op there.

    Each round hedges once: a draw that has held its page ``_HEDGE_AFTER_S``
    with no matching XHR starts the next country beside it, and the first
    non-empty result wins (the other is cancelled and its context closed).
    """
    attempts = max(1, _LISTING_MAX_ATTEMPTS)
    tried = 0
    while tried < attempts:
        first = tried
        captures: list[tuple[str, _Capture]] = []

        async def attempt(
            i: int, first: int = first, captures: list = captures
        ) -> list[dict[str, Any]]:
            abandon = None
            if i:
                primary = captures[0][1]
                why = await _hedge_wait(primary)
                if why:
                    logger.info("[tiktok] %s hedge skipped: %s", kind, why)
                    return []

                def abandon(primary: _Capture = primary) -> bool:
                    # Once the first draw has ended empty, this one is the draw.
                    return bool(primary.responses) and not primary.done

            country = country_for_rotation(first + i)
            capture = _Capture()
            captures.append((country, capture))
            await report_stage(f"{kind}: browser attempt {first + i + 1} ({country})")
            return await _draw(
                page_url,
                target_count,
                markers,
                extract,
                interact,
                country=country,
                capture=capture,
                headless=headless,
                kind=kind,
                abandon=abandon,
            )

        # 0 means no hedge, the same as TIKTOK_PAGE_HEDGE_S=0.
        hedge = _HEDGE_AFTER_S > 0 and first + 1 < attempts
        items = await hedged(
            attempt,
            after_s=_HEDGE_AFTER_S,
            accept=bool,
            max_extra=1 if hedge else 0,
            plugin=PLUGIN,
            stage=kind,
        )
        # A hedge that never navigated spent no exit.
        drawn = [(country, c) for country, c in captures if not c.skipped]
        tried += max(1, len(drawn))
        for country, capture in drawn:
            reason = _reason(capture)
            if reason in ("geo_block", "login"):
                _BAD_EXITS[country] += 1
                logger.warning(
                    "[tiktok] %s exit on country=%s (%d so far)",
                    reason,
                    country,
                    _BAD_EXITS[country],
                )
        if items or tried >= attempts:
            return items
        logger.info(
            "[tiktok] empty %s for %s (attempt %d/%d, country=%s, reason=%s); "
            "retrying on a fresh exit country",
            kind,
            logged_host(page_url),
            tried,
            attempts,
            ",".join(country for country, _ in drawn),
            ",".join(_reason(capture) for _, capture in drawn),
        )
    return []


def _listing_kind(page_url: str) -> str:
    path = urlsplit(page_url).path
    if path.startswith("/@"):
        return "profile"
    if path.startswith("/tag/"):
        return "hashtag"
    if path.startswith("/search"):
        return "search"
    return "listing"


async def fetch_item_list(page_url: str, target_count: int) -> list[dict[str, Any]]:
    """Return up to ``target_count`` itemStructs from a listing page's XHRs.

    Headful when ``CRAWL_HEADED_XVFB_ENABLED`` promises a display, headless
    otherwise so launch never fails. Retries empty draws across a spread of exit
    countries (``TIKTOK_LISTING_MAX_ATTEMPTS``) to escape a TikTok-flagged pool.
    """
    return await _fetch_with_rotation(
        page_url,
        target_count,
        _ITEM_LIST_MARKERS,
        items_from_response,
        _scroll_page,
        headless=not _HEADED,
        kind=_listing_kind(page_url),
    )


async def fetch_user_search(page_url: str, target_count: int) -> list[dict[str, Any]]:
    """Return up to ``target_count`` ``user_info`` records from a user-search page."""
    return await _fetch_with_rotation(
        page_url,
        target_count,
        _USER_SEARCH_MARKERS,
        users_from_response,
        _search_users,
        kind="user search",
    )


async def fetch_comments(page_url: str, target_count: int) -> list[dict[str, Any]]:
    """Return up to ``target_count`` raw comment records for a video.

    The unsigned comment API first (about 1.5 s); the video page's own XHRs in
    the browser only when it comes back empty or fails, which is also the alarm
    that TikTok started signing it.
    """
    if _COMMENTS_API:
        try:
            comments = await fetch_comments_api(page_url, target_count)
        except Exception as exc:
            logger.warning(
                "[tiktok] comments API failed (%s); falling back to the browser",
                type(exc).__name__,
            )
            comments = []
        if comments:
            logger.info(
                "[tiktok] comments fast path: %d comments over the API", len(comments)
            )
            return comments
        logger.info(
            "[tiktok] comments API came back empty for %s; falling back to the browser",
            logged_host(page_url),
        )
    slots = BROWSER_SLOTS.get()
    if slots is None:
        return await _browse_comments(page_url, target_count)
    async with slots:
        return await _browse_comments(page_url, target_count)


async def _browse_comments(page_url: str, target_count: int) -> list[dict[str, Any]]:
    return await _fetch_with_rotation(
        page_url,
        target_count,
        _COMMENT_MARKERS,
        comments_from_response,
        _scroll_comments,
        kind="comments",
    )


async def fetch_trending(page_url: str, target_count: int) -> list[dict[str, Any]]:
    """Return up to ``target_count`` trending itemStructs from the Explore feed.

    The unsigned Explore API first (about 2 s); the browser only when it comes
    back empty or fails, which is also the alarm that TikTok started signing it.
    """
    if _TRENDING_API:
        try:
            items = await fetch_trending_api(target_count)
        except Exception as exc:
            logger.warning(
                "[tiktok] trending API failed (%s); falling back to the browser",
                type(exc).__name__,
            )
            items = []
        if items:
            logger.info(
                "[tiktok] trending fast path: %d items over the API", len(items)
            )
            return items
        logger.info(
            "[tiktok] trending API came back empty; falling back to the browser"
        )
    return await _fetch_with_rotation(
        page_url,
        target_count,
        _EXPLORE_MARKERS,
        items_from_response,
        _scroll_page,
        kind="trending",
    )
