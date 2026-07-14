"""Video-URL flow: fetch a post page, read its rehydration blob, emit one item."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ..extraction import extract_rehydration_data, parse_video, video_item_struct
from ..extraction.timestamps import now_iso
from ..targets.types import TikTokTarget
from . import FetchFn


async def iter_video(
    target: TikTokTarget, *, fetch: FetchFn
) -> AsyncIterator[dict[str, Any]]:
    html = await fetch(target.url)
    if not html:
        return
    data = extract_rehydration_data(html)
    if not data:
        return
    item = video_item_struct(data)
    if item is None:
        return
    out = parse_video(item)
    out["scrapedAt"] = now_iso()
    yield out
