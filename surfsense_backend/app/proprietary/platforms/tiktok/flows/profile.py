"""Profile flow: reliable blob metadata first, then the (gated) video listing.

A profile's account data (name, followers, bio, verification) lives in the page's
rehydration blob and loads over plain HTTP without a signed request, so we emit it
first and always. The video listing needs a signed ``item_list`` XHR that TikTok
withholds from anonymous sessions, so it is best-effort: it streams videos when it
loads and degrades to an ErrorItem (via :func:`iter_listing`) when withheld. The
metadata item therefore survives even when the videos are blocked.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ..extraction import extract_rehydration_data, parse_profile, user_info
from ..extraction.timestamps import now_iso
from ..targets.types import TikTokTarget
from . import FetchFn, FetchListingFn
from .listing import iter_listing


async def iter_profile(
    target: TikTokTarget,
    *,
    cap: int,
    fetch: FetchFn,
    fetch_listing: FetchListingFn,
) -> AsyncIterator[dict[str, Any]]:
    html = await fetch(target.url)
    info = user_info(extract_rehydration_data(html) or {}) if html else None
    if info:
        item = parse_profile(info)
        item["scrapedAt"] = now_iso()
        yield item
    async for out in iter_listing(target, cap=cap, fetch_listing=fetch_listing):
        yield out
