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
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from proprietary.scraping.logged_host import logged_host

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
    parse_translation,
    parse_video_page,
)
from .schemas import CommentItem, YouTubeCommentsInput
from .scraper import _post, _published_date, fan_out
from .url_resolver import resolve_url

logger = logging.getLogger(__name__)

# Apify sort value -> YouTube sort-menu label. The section token loads "Top" by
# default, so only "Newest" needs an explicit switch request.
_SORT_LABELS = {"TOP_COMMENTS": "Top", "NEWEST_FIRST": "Newest"}

# Seed from ``/next {videoId}`` (the same section token, title and count as the
# watch page, at about a third of the bytes and with no HTML scan).
# YOUTUBE_COMMENTS_NEXT_SEED=0 restores the watch-page seed.
_NEXT_SEED = os.getenv("YOUTUBE_COMMENTS_NEXT_SEED", "1") != "0"


async def _post_next(token: str) -> dict[str, Any] | None:
    return await _post(
        INNERTUBE_NEXT_URL, build_innertube_payload(continuation_token=token)
    )


def _finalize(
    partial: dict[str, Any], base: dict[str, Any], reply_to: str | None
) -> dict:
    return CommentItem(**{**base, **partial, "replyToCid": reply_to}).to_output()


def _older(entity: dict[str, Any], cutoff) -> bool:
    when = _published_date(entity.get("publishedTimeText"))
    return when is not None and when < cutoff


async def _collect_replies(
    token: str | None, *, parent_cid: str, base: dict[str, Any], cutoff, budget: int
) -> tuple[list[dict], str | None]:
    """Collect one thread's replies (``replyLevel`` 1), page by page.

    Stops once ``budget`` replies are in hand (a thread can hold thousands) and
    returns the token of the next page, so the caller can go on if budget is
    left over.
    """
    replies: list[dict] = []
    while token and len(replies) < budget:
        data = await _post_next(token)
        if not data:
            return replies, None
        for entity in parse_comment_entities(data):
            if cutoff and _older(entity, cutoff):
                continue
            replies.append(_finalize(entity, base, parent_cid))
        token = comment_next_token(data)
    return replies, token


def _reply_plan(
    entities: list[dict[str, Any]], reply_tokens: dict[str, str], budget: int
) -> list[tuple[str, str, int]]:
    """The reply threads the remaining ``budget`` can reach, with a budget each.

    Walks the page in emit order: each comment costs one item, then its thread
    up to its ``replyCount`` (an estimate: rounded above 1K, at least one when a
    reply token exists). Threads past the budget are not fetched.
    """
    plan: list[tuple[str, str, int]] = []
    for entity in entities:
        if budget <= 0:
            break
        budget -= 1
        token = reply_tokens.get(entity["cid"])
        if token and budget > 0:
            plan.append((entity["cid"], token, budget))
            budget -= min(max(entity.get("replyCount") or 0, 1), budget)
    return plan


async def _seed(video_id: str) -> tuple[str | None, dict[str, Any]]:
    """The comments-section token plus the video's title and approximate count."""
    if _NEXT_SEED:
        data = await _post(
            INNERTUBE_NEXT_URL, build_innertube_payload(video_id=video_id)
        )
        # No token may be a /next layout we do not read (an A/B or consent
        # variant), not comments turned off: the watch page decides.
        section = comment_section_token(data) if data else None
        if section:
            contextual = find_first(data, "contextualInfo")
            return section, {
                # parse_translation reads the /next title; with hl=en it is
                # the plain title.
                "title": parse_translation(data)[0],
                "commentsCount": parse_count(dig(contextual, "runs", 0, "text")),
            }
    html = await fetch_html(f"https://www.youtube.com/watch?v={video_id}")
    if not html:
        return None, {}
    # Both helpers scan 1-2MB of watch-page HTML in pure Python; keep that
    # off the event loop.
    initial = await asyncio.to_thread(extract_yt_initial_data, html)
    if not initial:
        return None, {}
    section = comment_section_token(initial)
    if not section:  # comments disabled or absent: skip the page parse
        return None, {}
    meta = await asyncio.to_thread(parse_video_page, html) or {}
    return section, meta


async def _comments_for_video(
    video_id: str, input_model: YouTubeCommentsInput
) -> AsyncIterator[dict]:
    limit = input_model.maxComments
    page_url = f"https://www.youtube.com/watch?v={video_id}"
    section, meta = await _seed(video_id)
    if not section:  # comments disabled or absent
        return
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

        # Fetch the reply threads the budget can reach concurrently (the reused
        # session multiplexes requests), then emit in Apify order: comment, its
        # replies.
        plan = _reply_plan(entities, reply_tokens, limit - count)
        fetched = await asyncio.gather(
            *(
                _collect_replies(
                    tok, parent_cid=cid, base=base, cutoff=cutoff, budget=budget
                )
                for cid, tok, budget in plan
            )
        )
        replies_by_cid = {cid: r for (cid, _, _), r in zip(plan, fetched, strict=True)}

        for entity in entities:
            if count >= limit:
                return
            # Newest-first: the first too-old comment means the rest are older.
            if cutoff and _older(entity, cutoff):
                return
            yield _finalize(entity, base, None)
            count += 1

            cid = entity["cid"]
            replies, more = replies_by_cid.get(cid, ([], reply_tokens.get(cid)))
            while True:
                for reply in replies:
                    if count >= limit:
                        return
                    yield reply
                    count += 1
                # The estimate undershot (or the thread was past the plan) and
                # budget is left: fetch on, lazily.
                if not more or count >= limit:
                    break
                replies, more = await _collect_replies(
                    more, parent_cid=cid, base=base, cutoff=cutoff, budget=limit - count
                )

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
            logger.warning(
                "Comments: not a video URL on %s, skipping", logged_host(entry.url)
            )
            continue
        jobs.append(_comments_for_video(resolved.value, input_model))
    async for comment in fan_out(jobs):
        yield comment


async def scrape_comments(
    input_model: YouTubeCommentsInput,
    *,
    limit: int | None = None,
    on_item: Callable[[int], Awaitable[None]] | None = None,
) -> list[dict]:
    """Collect :func:`iter_comments` into a list, honoring an optional guard.

    ``on_item`` hears the count after each comment, for the caller's progress.
    """
    results: list[dict] = []
    async for comment in iter_comments(input_model):
        results.append(comment)
        if on_item is not None:
            await on_item(len(results))
        if limit is not None and len(results) >= limit:
            break
    return results
