"""Listing flow shared by profile, hashtag, and search targets.

The browser seam returns raw itemStructs captured from the signed ``item_list``
XHRs; this maps each to the output contract, drops duplicate video ids, and
stops at the per-target ``cap``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ..extraction import parse_video
from ..extraction.timestamps import now_iso
from ..targets.types import TikTokTarget
from . import FetchListingFn


async def iter_listing(
    target: TikTokTarget, *, cap: int, fetch_listing: FetchListingFn
) -> AsyncIterator[dict[str, Any]]:
    if cap <= 0:
        return
    seen: set[str] = set()
    emitted = 0
    for item in await fetch_listing(target.url, cap):
        out = parse_video(item)
        video_id = out.get("id")
        if video_id is not None:
            if video_id in seen:
                continue
            seen.add(video_id)
        out["scrapedAt"] = now_iso()
        yield out
        emitted += 1
        if emitted >= cap:
            return
