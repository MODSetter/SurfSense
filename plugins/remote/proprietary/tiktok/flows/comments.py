"""Comments flow: a video URL -> its public comment thread.

Comments come from ``/api/comment/list``: unsigned over HTTP first, else the XHR
the video page fires once its comments panel is opened. Records are deduped by
comment id, capped, and — when a video has none or withholds them — degraded to
one ErrorItem, mirroring the listing flow.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ..extraction import parse_comment
from ..extraction.timestamps import now_iso
from ..schemas import ErrorItem
from ..targets.types import TikTokTarget
from . import FetchCommentsFn

# Every draw came back empty. Live, that is TikTok withholding the thread far more
# often than a video without comments, so say so first.
_EMPTY_MESSAGE = (
    "TikTok withheld this video's comments from every anonymous exit tried; try "
    "again later. If the video shows no comments on TikTok either, it has none or "
    "comments are turned off."
)


async def iter_comments(
    target: TikTokTarget, *, cap: int, fetch_comments: FetchCommentsFn
) -> AsyncIterator[dict[str, Any]]:
    if cap <= 0:
        return
    seen: set[str] = set()
    emitted = 0
    for raw in await fetch_comments(target.url, cap):
        out = parse_comment(raw, target.url)
        cid = out.get("id")
        if cid is not None:
            if cid in seen:
                continue
            seen.add(cid)
        out["scrapedAt"] = now_iso()
        yield out
        emitted += 1
        if emitted >= cap:
            return
    if emitted == 0:
        yield ErrorItem(
            url=target.url,
            input=target.value,
            error=_EMPTY_MESSAGE,
            errorCode="no_comments",
            scrapedAt=now_iso(),
        ).to_output()
