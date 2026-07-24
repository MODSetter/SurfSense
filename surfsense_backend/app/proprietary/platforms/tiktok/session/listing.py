"""Browser-driven listing fetch: let TikTok sign its own ``item_list`` XHRs.

Profile/hashtag/search listings need signed requests (``X-Gnarly``) whose
algorithm rev's monthly and reads a browser canvas fingerprint. Rather than port
and chase that signer, we load the page in the stealth browser we already run
(patchright-Chromium, via the web-crawler tier) and capture the itemStruct JSON
the page's own scripts fetch while scrolling. The browser is the client, so it
signs correctly for whatever version TikTok ships.

The pure response-shape parsing lives in :func:`items_from_response`; this module
is the untested browser-I/O glue (covered by the e2e smoke, not unit tests).

Needs a residential proxy; datacenter IPs get empty bodies and 429s. TikTok also
withholds the feed (empty 200, or a redirect to /login) from the provider's
unpinned worldwide pool, so :func:`_fetch_with_rotation` walks country-pinned
exits until a draw is non-empty — the same escape the Reddit/ttwid warm path uses
(see :mod:`app.utils.proxy.rotation`).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

from scrapling.fetchers import StealthyFetcher

from app.config import config
from app.proprietary.web_crawler.stealth import (
    build_stealthy_kwargs,
    get_stealth_config,
)
from app.utils.proxy import get_geo_proxy_url
from app.utils.proxy.rotation import country_for_rotation

from ..extraction import (
    comments_from_response,
    items_from_response,
    users_from_response,
)

logger = logging.getLogger(__name__)

ExtractFn = Callable[[Any], list[dict[str, Any]]]
# Drives the page after navigation to trigger/paginate the target XHRs, filling
# ``collected`` until it reaches ``target_count`` (or the interaction gives up).
InteractFn = Callable[[Any, list[dict[str, Any]], int], None]

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
_COMMENT_ICON_SELECTORS = (
    '[data-e2e="comment-icon"]',
    '[data-e2e="browse-comment"]',
)
# The comment icon hydrates a beat after DOM-ready; wait for it before clicking.
_COMMENT_ICON_WAIT_MS = 8000
# First comment page lands shortly after the click — don't declare "empty" early.
_COMMENT_FIRST_PAGE_MS = 3500
_HOME_URL = "https://www.tiktok.com/"
_MSTOKEN_COOKIE = "msToken"
# Bounded scroll: a dead page can't loop forever, and a live one stops early
# once enough items are captured.
_SCROLL_MAX_ROUNDS = 20
_SCROLL_SETTLE_MS = 1500
# Warm-up poll for the anonymous msToken cookie the item_list API requires.
_WARM_POLLS = 8
_WARM_POLL_MS = 500


def _has_mstoken(page: Any) -> bool:
    try:
        return any(c.get("name") == _MSTOKEN_COOKIE for c in page.context.cookies())
    except Exception:
        return False


def _dismiss_login_modal(page: Any) -> None:
    """Close the login modal that blocks scrolling; Escape as fallback.

    Only the modal's own close button, never a generic dialog button (avoids
    clicking "Log in").
    """
    try:
        closed = page.evaluate(
            """() => {
              const btn = document.querySelector('[data-e2e="modal-close-inner-button"]');
              if (btn) { btn.click(); return true; }
              return false;
            }"""
        )
        if not closed:
            page.keyboard.press("Escape")
    except Exception:
        pass


def _scroll_page(page: Any, collected: list[dict[str, Any]], target_count: int) -> None:
    """Page down a listing feed until enough items are captured or it stops growing."""
    last_height = 0
    for _ in range(_SCROLL_MAX_ROUNDS):
        if len(collected) >= target_count:
            break
        _dismiss_login_modal(page)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(_SCROLL_SETTLE_MS)
        height = page.evaluate("document.body.scrollHeight")
        if not height or height <= last_height:
            break
        last_height = height


def _open_comments(page: Any) -> None:
    """Click the comment icon so the first ``/api/comment/list`` XHR fires.

    The icon must be present and interactive first (the SPA hydrates it a beat
    after DOM-ready), so we wait for it, then fall back to a JS click if the
    normal click is intercepted (cookie banner / overlay).
    """
    for selector in _COMMENT_ICON_SELECTORS:
        try:
            page.wait_for_selector(selector, timeout=_COMMENT_ICON_WAIT_MS)
        except Exception:
            continue
        try:
            page.click(selector, timeout=_COMMENT_ICON_WAIT_MS)
            return
        except Exception:
            try:
                page.eval_on_selector(selector, "el => el.click()")
                return
            except Exception:
                continue


def _scroll_comments(
    page: Any, collected: list[dict[str, Any]], target_count: int
) -> None:
    """Open the comments panel, then scroll its last comment into view to paginate.

    Comment XHRs fire only after the panel is opened, and paging must scroll the
    panel (not the page, which would advance the video feed), so we anchor on the
    last ``comment-level-1`` element. ponytail: naive scroll-to-last paging,
    bounded by ``_SCROLL_MAX_ROUNDS``; upgrade to container-height tracking if
    deep threads under-fetch.
    """
    _open_comments(page)
    # The panel's first page lands a beat after the click; give it room before
    # we decide there are no comments to page through.
    page.wait_for_timeout(_COMMENT_FIRST_PAGE_MS)
    for _ in range(_SCROLL_MAX_ROUNDS):
        if len(collected) >= target_count:
            break
        moved = page.evaluate(
            """() => {
              const items = document.querySelectorAll('[data-e2e="comment-level-1"]');
              if (!items.length) return false;
              items[items.length - 1].scrollIntoView({block: 'end'});
              return true;
            }"""
        )
        page.wait_for_timeout(_SCROLL_SETTLE_MS)
        if not moved:
            break


def _build_page_action(
    collected: list[dict[str, Any]],
    url: str,
    target_count: int,
    markers: tuple[str, ...],
    extract: ExtractFn,
    interact: InteractFn,
):
    """A sync ``page_action`` that warms the session then captures matching XHRs.

    A cold context returns an empty body, so we first mint the anonymous
    ``msToken`` (homepage hit), then navigate to the target with the listener
    already attached so page-one fires into it; ``interact`` pages the rest.
    ``markers``/``extract`` select which XHRs to keep and how to unwrap them.
    """

    def _on_response(response: Any) -> None:
        response_url = getattr(response, "url", "")
        if not any(marker in response_url for marker in markers):
            return
        try:
            body = response.json()
        except Exception:
            # An empty 200 (TikTok soft-block) or a body evicted before read.
            return
        collected.extend(extract(body))

    def _warm(page: Any) -> None:
        if _has_mstoken(page):
            return
        page.goto(_HOME_URL, wait_until="domcontentloaded")
        for _ in range(_WARM_POLLS):
            page.wait_for_timeout(_WARM_POLL_MS)
            if _has_mstoken(page):
                break

    def page_action(page: Any) -> Any:
        page.on("response", _on_response)
        try:
            _warm(page)
            # Navigate (back) to the target with the listener attached and a
            # token in hand, so the page-one XHR fires into the capture.
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(_SCROLL_SETTLE_MS)
            interact(page, collected, target_count)
        except Exception as exc:
            logger.debug("[tiktok] capture interaction aborted: %s", exc)
        return page

    return page_action


def _primer_url(url: str) -> str:
    """A tiny same-origin URL (``/robots.txt``) for the initial navigation.

    Scrapling's outer ``page.goto`` waits for the ``load`` event, which TikTok's
    SPA feed pages never fire — so navigating straight to the target burns the
    full 30s timeout every fetch. Priming on ``robots.txt`` (a plain-text 200 that
    fires ``load`` at once, same origin so referer/cookies stay coherent) lets the
    ``page_action`` then reach the real target with ``domcontentloaded`` — ~4x
    faster on profile feeds with no loss of capture.
    """
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}/robots.txt"


def _fetch_sync(
    url: str,
    target_count: int,
    markers: tuple[str, ...],
    extract: ExtractFn,
    interact: InteractFn,
    *,
    proxy: str | None,
    headless: bool = True,
) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    kwargs = build_stealthy_kwargs(get_stealth_config())
    StealthyFetcher.fetch(
        _primer_url(url),
        headless=headless,
        network_idle=False,
        proxy=proxy,
        page_action=_build_page_action(
            collected, url, target_count, markers, extract, interact
        ),
        **kwargs,
    )
    return collected[:target_count]


async def _fetch_with_rotation(
    page_url: str,
    target_count: int,
    markers: tuple[str, ...],
    extract: ExtractFn,
    interact: InteractFn,
    *,
    headless: bool = True,
) -> list[dict[str, Any]]:
    """Capture matching XHRs, walking exit *countries* until a draw is non-empty.

    TikTok withholds ``item_list``/``comment`` bodies from DataImpulse's unpinned
    worldwide pool (the pool ``PROXY_URL`` uses for SERP health) but serves them on
    country-pinned exits, so each empty draw retries on a fresh country rather than
    the same flagged pool (see :mod:`app.utils.proxy.rotation`). Non-geo providers
    ignore the country and re-draw their one URL, so this stays a safe no-op there.
    """
    attempts = max(1, config.TIKTOK_LISTING_MAX_ATTEMPTS)
    for attempt in range(attempts):
        proxy = get_geo_proxy_url(country_for_rotation(attempt))
        items = await asyncio.to_thread(
            _fetch_sync,
            page_url,
            target_count,
            markers,
            extract,
            interact,
            proxy=proxy,
            headless=headless,
        )
        if items or attempt == attempts - 1:
            return items
        logger.info(
            "[tiktok] empty %s for %s (attempt %d/%d); retrying on a fresh exit country",
            markers[0],
            page_url,
            attempt + 1,
            attempts,
        )
    return []


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
        headless=not config.CRAWL_HEADED_XVFB_ENABLED,
    )


async def fetch_user_search(page_url: str, target_count: int) -> list[dict[str, Any]]:
    """Return up to ``target_count`` ``user_info`` records from a user-search page."""
    return await _fetch_with_rotation(
        page_url,
        target_count,
        _USER_SEARCH_MARKERS,
        users_from_response,
        _scroll_page,
    )


async def fetch_comments(page_url: str, target_count: int) -> list[dict[str, Any]]:
    """Return up to ``target_count`` raw comment records from a video page's XHRs."""
    return await _fetch_with_rotation(
        page_url,
        target_count,
        _COMMENT_MARKERS,
        comments_from_response,
        _scroll_comments,
    )


async def fetch_trending(page_url: str, target_count: int) -> list[dict[str, Any]]:
    """Return up to ``target_count`` trending itemStructs from the Explore feed."""
    return await _fetch_with_rotation(
        page_url,
        target_count,
        _EXPLORE_MARKERS,
        items_from_response,
        _scroll_page,
    )
