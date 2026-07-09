"""Browser-driven listing fetch: let TikTok sign its own ``item_list`` XHRs.

Profile/hashtag/search listings need signed requests (``X-Gnarly``) whose
algorithm rev's monthly and reads a browser canvas fingerprint. Rather than port
and chase that signer, we load the page in the stealth browser we already run
(patchright-Chromium, via the web-crawler tier) and capture the itemStruct JSON
the page's own scripts fetch while scrolling. The browser is the client, so it
signs correctly for whatever version TikTok ships.

The pure response-shape parsing lives in :func:`items_from_response`; this module
is the untested browser-I/O glue (covered by the e2e smoke, not unit tests).

Needs a residential proxy; datacenter IPs get empty bodies and 429s. The profile
feed (``/api/post/item_list``) is additionally soft-blocked: TikTok returns an
empty 200 even to its own signed request, so profile targets yield nothing.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from scrapling.fetchers import StealthyFetcher

from app.proprietary.web_crawler.stealth import (
    build_stealthy_kwargs,
    get_stealth_config,
)
from app.utils.proxy import get_proxy_url

from ..extraction import items_from_response, users_from_response

logger = logging.getLogger(__name__)

ExtractFn = Callable[[Any], list[dict[str, Any]]]

# XHR paths that carry itemStructs for the three listing kinds.
_ITEM_LIST_MARKERS = (
    "/api/post/item_list",
    "/api/challenge/item_list",
    "/api/search/",
)
# The user-search XHR carries account records (user_list), not itemStructs.
_USER_SEARCH_MARKERS = ("/api/search/user",)
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


def _build_page_action(
    collected: list[dict[str, Any]],
    url: str,
    target_count: int,
    markers: tuple[str, ...],
    extract: ExtractFn,
):
    """A sync ``page_action`` that warms the session then captures matching XHRs.

    A cold context returns an empty body, so we first mint the anonymous
    ``msToken`` (homepage hit), then navigate to the target with the listener
    already attached so page-one fires into it; scrolling pages the rest.
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
            # token in hand, so the page-one item_list fires into the capture.
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(_SCROLL_SETTLE_MS)
            last_height = 0
            for _ in range(_SCROLL_MAX_ROUNDS):
                if len(collected) >= target_count:
                    break
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(_SCROLL_SETTLE_MS)
                height = page.evaluate("document.body.scrollHeight")
                if not height or height <= last_height:
                    break
                last_height = height
        except Exception as exc:
            logger.debug("[tiktok] listing scroll aborted: %s", exc)
        return page

    return page_action


def _fetch_sync(
    url: str, target_count: int, markers: tuple[str, ...], extract: ExtractFn
) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    kwargs = build_stealthy_kwargs(get_stealth_config())
    StealthyFetcher.fetch(
        url,
        headless=True,
        network_idle=False,
        proxy=get_proxy_url(),
        page_action=_build_page_action(
            collected, url, target_count, markers, extract
        ),
        **kwargs,
    )
    return collected[:target_count]


async def fetch_item_list(page_url: str, target_count: int) -> list[dict[str, Any]]:
    """Return up to ``target_count`` itemStructs from a listing page's XHRs."""
    return await asyncio.to_thread(
        _fetch_sync, page_url, target_count, _ITEM_LIST_MARKERS, items_from_response
    )


async def fetch_user_search(page_url: str, target_count: int) -> list[dict[str, Any]]:
    """Return up to ``target_count`` ``user_info`` records from a user-search page."""
    return await asyncio.to_thread(
        _fetch_sync, page_url, target_count, _USER_SEARCH_MARKERS, users_from_response
    )
