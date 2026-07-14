"""Comments flow: a video URL -> its public comment thread.

Comments load over a signed ``/api/comment/list`` XHR that TikTok *does* serve to
anonymous sessions once the comments panel is opened (unlike profile-video/search
feeds). Records are deduped by comment id, capped, and — when a video has none or
withholds them — degraded to one ErrorItem, mirroring the listing flow.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ..extraction import parse_comment
from ..extraction.timestamps import now_iso
from ..schemas import ErrorItem
from ..targets.types import TikTokTarget
from . import FetchCommentsFn

_EMPTY_MESSAGE = (
    "No comments returned. The video may have none, comments disabled, or TikTok "
    "withheld them from anonymous access."
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
