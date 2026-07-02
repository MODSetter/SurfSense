"""Orchestrator for the YouTube Comments scraper (Apify-compatible).

Distinct from the video scraper: one output item per top-level comment *and*
per reply, sourced from the InnerTube ``/next`` endpoint. The watch page seeds a
comments-section continuation; ``/next`` then returns comment entity payloads,
per-thread reply tokens, and the paging token. ``maxComments`` counts every
emitted item (comments + replies), matching Apify.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from .innertube import INNERTUBE_NEXT_URL, build_innertube_payload, fetch_html
from .parsers import (
    comment_next_token,
    comment_reply_tokens,
    comment_section_token,
    comment_sort_tokens,
    dig,
    extract_yt_initial_data,
    find_first,
    parse_comment_entities,
    parse_count,
    parse_video_page,
)
from .scraper import _post, _published_date, fan_out
from .schemas import CommentItem, YouTubeCommentsInput
from .url_resolver import resolve_url

logger = logging.getLogger(__name__)

# Apify sort value -> YouTube sort-menu label. The section token loads "Top" by
# default, so only "Newest" needs an explicit switch request.
_SORT_LABELS = {"TOP_COMMENTS": "Top", "NEWEST_FIRST": "Newest"}


async def _post_next(token: str) -> dict[str, Any] | None:
    return await _post(INNERTUBE_NEXT_URL, build_innertube_payload(continuation_token=token))


def _finalize(partial: dict[str, Any], base: dict[str, Any], reply_to: str | None) -> dict:
    return CommentItem(**{**base, **partial, "replyToCid": reply_to}).to_output()


def _older(entity: dict[str, Any], cutoff) -> bool:
    when = _published_date(entity.get("publishedTimeText"))
    return when is not None and when < cutoff


async def _collect_replies(
    token: str, *, parent_cid: str, base: dict[str, Any], cutoff
) -> list[dict]:
    """Collect one thread's replies (``replyLevel`` 1) until exhausted."""
    replies: list[dict] = []
    while token:
        data = await _post_next(token)
        if not data:
            break
        for entity in parse_comment_entities(data):
            if cutoff and _older(entity, cutoff):
                continue
            replies.append(_finalize(entity, base, parent_cid))
        token = comment_next_token(data)
    return replies


async def _comments_for_video(
    video_id: str, input_model: YouTubeCommentsInput
) -> AsyncIterator[dict]:
    limit = input_model.maxComments
    page_url = f"https://www.youtube.com/watch?v={video_id}"
    html = await fetch_html(page_url)
    if not html:
        return
    initial = extract_yt_initial_data(html)
    if not initial:
        return
    section = comment_section_token(initial)
    if not section:  # comments disabled or absent
        return

    meta = parse_video_page(html) or {}
    base = {
        "videoId": video_id,
        "pageUrl": page_url,
        "title": meta.get("title"),
        "commentsCount": meta.get("commentsCount"),
    }

    data = await _post_next(section)
    if not data:
        return

    # Authoritative total lives in the comments-section header (exact integer),
    # not the watch-page HTML where the count is lazy-loaded / absent.
    header = find_first(data, "commentsHeaderRenderer")
    if header:
        base["commentsCount"] = parse_count(dig(header, "countText", "runs", 0, "text"))

    # oldestCommentDate forces newest-first (Apify behavior).
    cutoff = _published_date(input_model.oldestCommentDate)
    sort = "NEWEST_FIRST" if cutoff else input_model.sortCommentsBy
    label = _SORT_LABELS[sort]
    if label == "Newest":
        sort_tokens = comment_sort_tokens(data)
        if label in sort_tokens:
            switched = await _post_next(sort_tokens[label])
            if switched:
                data = switched

    count = 0
    while data:
        reply_tokens = comment_reply_tokens(data)
        entities = parse_comment_entities(data)

        # Fetch this page's reply threads concurrently (the reused session
        # multiplexes requests), then emit in Apify order: comment, its replies.
        # ponytail: prefetch is capped at the remaining budget — each thread
        # yields >=1 item, so more threads than budget can't all be needed.
        pending = [
            (e["cid"], reply_tokens[e["cid"]])
            for e in entities
            if e["cid"] in reply_tokens
        ][: max(limit - count, 0)]
        fetched = await asyncio.gather(
            *(
                _collect_replies(tok, parent_cid=cid, base=base, cutoff=cutoff)
                for cid, tok in pending
            )
        )
        replies_by_cid = {cid: r for (cid, _), r in zip(pending, fetched)}

        for entity in entities:
            if count >= limit:
                return
            # Newest-first: the first too-old comment means the rest are older.
            if cutoff and _older(entity, cutoff):
                return
            yield _finalize(entity, base, None)
            count += 1

            for reply in replies_by_cid.get(entity["cid"], []):
                if count >= limit:
                    return
                yield reply
                count += 1

        token = comment_next_token(data)
        if not token or count >= limit:
            return
        data = await _post_next(token)


async def iter_comments(input_model: YouTubeCommentsInput) -> AsyncIterator[dict]:
    """Yield Apify-shaped comment items for every startUrl video.

    Videos are scraped concurrently (each video's own comment paging stays
    sequential), which is the dominant speedup when reviewing many videos.
    """
    jobs = []
    for entry in input_model.startUrls:
        resolved = resolve_url(entry.url)
        if not resolved or resolved.kind != "video":
            logger.warning("Comments: not a video URL, skipping: %s", entry.url)
            continue
        jobs.append(_comments_for_video(resolved.value, input_model))
    async for comment in fan_out(jobs):
        yield comment


async def scrape_comments(
    input_model: YouTubeCommentsInput, *, limit: int | None = None
) -> list[dict]:
    """Collect :func:`iter_comments` into a list, honoring an optional guard."""
    results: list[dict] = []
    async for comment in iter_comments(input_model):
        results.append(comment)
        if limit is not None and len(results) >= limit:
            break
    return results
