"""Orchestrator for the Reddit scraper.

The core is the async generator :func:`iter_reddit` (unbounded, ``after``-cursor
paged); :func:`scrape_reddit` is a thin collector with a caller-supplied
``limit`` guard. Any cap is caller policy, never baked into flow logic.

Independent targets (one per ``startUrl`` / search) fan out concurrently on a
pool of warm ``loid`` sessions (sticky IPs); each target's own ``after`` paging
stays sequential. ``fan_out`` is ported from ``../youtube/scraper.py`` but bound
to *this* module's proxy holders so every worker warms its own ``loid`` once and
reuses it — the ~10-50x throughput win over a browser design.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from .fetch import (
    RedditAccessBlockedError,
    bind_proxy_holder,
    fetch_json,
    now_iso,
    open_proxy_holder,
)
from .parsers import (
    _before,
    after,
    children,
    flatten_comments,
    parse_comment,
    parse_community,
    parse_post,
)
from .schemas import RedditItem, RedditScrapeInput
from .url_resolver import ResolvedUrl, resolve_url

logger = logging.getLogger(__name__)

__all__ = [
    "RedditAccessBlockedError",
    "iter_reddit",
    "scrape_reddit",
]

# Independent jobs run concurrently on a pool of warm proxy sessions. Matches
# the youtube sibling; 16 workers saturate typical job counts while leaving
# gateway headroom.
_FANOUT_CONCURRENCY = 16

# Reddit caps any listing at ~1000 items (100/page => ~10 pages). Stop there so
# a runaway target can't page forever.
_LISTING_LIMIT = 100
_MAX_PAGES = 10
_EMPTY_STREAK_ABORT = 2

# A subreddit's per-post comment fetches are independent (each is a separate
# .json), so after paging the listing on one sticky IP we fan them across their
# own warm sessions instead of walking them sequentially — the dominant cost of
# a subreddit+comments scrape (~3.6x on the comment phase; scripts/_bench_reddit2).
# Kept below the top-level fan-out width: with N concurrent subreddit targets the
# worst case is N x this many proxy IPs, so this bounds that multiplication.
_COMMENT_CONCURRENCY = 8

# Search sorts differ from listing sorts; fall back to "new" for a listing path
# when the input carries a search-only sort.
_LISTING_SORTS = frozenset({"hot", "new", "top", "rising", "controversial", "best"})


async def fan_out(
    jobs: list[AsyncIterator[dict[str, Any]]], *, concurrency: int = _FANOUT_CONCURRENCY
) -> AsyncIterator[dict[str, Any]]:
    """Stream items from independent async-iterator jobs via a warm worker pool.

    Each worker opens ONE proxy session and reuses it across the sequential jobs
    it pulls, so only the first job per worker pays the proxy handshake + the
    ``loid`` warm-up. A bad job yields nothing rather than aborting the batch;
    workers are cancelled and their sessions closed if the consumer stops early.
    """
    if not jobs:
        return
    job_queue: asyncio.Queue[AsyncIterator[dict[str, Any]]] = asyncio.Queue()
    for job in jobs:
        job_queue.put_nowait(job)
    results: asyncio.Queue[list[dict[str, Any]]] = asyncio.Queue()

    async def worker() -> None:
        holder = None
        try:
            holder = await open_proxy_holder()
        except Exception as e:  # no session: jobs still run via one-shot fetches
            logger.warning("[reddit] proxy session open failed: %s", e)
        try:
            while True:
                try:
                    job = job_queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                items: list[dict[str, Any]] = []
                try:
                    if holder is not None:
                        async with bind_proxy_holder(holder):
                            items = [item async for item in job]
                    else:
                        items = [item async for item in job]
                except Exception as e:  # one bad target must not kill the run
                    logger.warning("[reddit] fan-out job failed: %s", e)
                await results.put(items)
        finally:
            if holder is not None:
                await holder.close()

    tasks = [asyncio.create_task(worker()) for _ in range(min(concurrency, len(jobs)))]
    try:
        for _ in range(len(jobs)):
            for item in await results.get():
                yield item
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def _emit(partial: dict[str, Any], *, include_nsfw: bool) -> dict[str, Any] | None:
    """Stamp ``scrapedAt``, apply the NSFW gate, and wrap as an output dict."""
    if not include_nsfw and partial.get("over18") is True:
        return None
    return RedditItem(**{**partial, "scrapedAt": now_iso()}).to_output()


async def _paginate_listing(
    path: str,
    base_params: dict[str, Any],
    kinds: frozenset[str],
    *,
    max_items: int,
    include_nsfw: bool,
    date_limit: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Yield raw child ``data`` dicts across pages via the ``after`` cursor.

    Filters by child ``kind`` (``t3``/``t1``), the NSFW gate, and ``date_limit``
    (drops older items and, since ``date_limit`` forces newest-first, stops once
    a page crosses the cutoff). Aborts on an empty-streak, a null ``after``, or
    the ~1000-item page ceiling.
    """
    if max_items <= 0:
        return
    emitted = 0
    cursor: str | None = None
    empty_streak = 0
    for _page in range(_MAX_PAGES):
        params = {**base_params, "limit": _LISTING_LIMIT}
        if cursor:
            params["after"] = cursor
        listing = await fetch_json(path, params)
        kids = children(listing)
        if not kids:
            empty_streak += 1
            if empty_streak >= _EMPTY_STREAK_ABORT:
                break
        else:
            empty_streak = 0
        crossed_cutoff = False
        for child in kids:
            if not isinstance(child, dict) or child.get("kind") not in kinds:
                continue
            data = child.get("data") or {}
            if date_limit and _before(data.get("created_utc"), date_limit):
                crossed_cutoff = True
                continue
            if not include_nsfw and data.get("over_18") is True:
                continue
            yield data
            emitted += 1
            if emitted >= max_items:
                return
        cursor = after(listing)
        if not cursor or crossed_cutoff:
            break


async def _post_flow(
    post_id: str,
    *,
    input_model: RedditScrapeInput,
    subreddit: str | None = None,
    include_post: bool = True,
) -> AsyncIterator[dict[str, Any]]:
    """Emit a post (unless ``include_post`` is False) plus its comment tree."""
    path = f"r/{subreddit}/comments/{post_id}" if subreddit else f"comments/{post_id}"
    data = await fetch_json(path)
    if not isinstance(data, list) or not data:
        return
    post_children = children(data[0])
    if include_post and post_children:
        item = _emit(parse_post(post_children[0]), include_nsfw=input_model.includeNSFW)
        if item is not None:
            yield item
    if input_model.skipComments or len(data) < 2:
        return
    flat = flatten_comments(
        children(data[1]),
        max_comments=input_model.maxComments,
        date_limit=input_model.commentDateLimit,
    )
    for comment in flat:
        item = _emit(comment, include_nsfw=input_model.includeNSFW)
        if item is not None:
            yield item


async def _subreddit_flow(
    subreddit: str,
    *,
    input_model: RedditScrapeInput,
    sort: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Emit the community, then paged posts (descending into comments if asked)."""
    if not input_model.skipCommunity:
        about = await fetch_json(f"r/{subreddit}/about")
        if isinstance(about, dict):
            item = _emit(parse_community(about), include_nsfw=input_model.includeNSFW)
            if item is not None:
                yield item

    # postDateLimit forces newest-first so the early-stop is correct.
    sort = "new" if input_model.postDateLimit else (sort or input_model.sort)
    if sort not in _LISTING_SORTS:
        sort = "new"
    params: dict[str, Any] = {}
    if sort == "top" and input_model.time:
        params["t"] = input_model.time

    post_ids: list[str] = []
    async for data in _paginate_listing(
        f"r/{subreddit}/{sort}",
        params,
        frozenset({"t3"}),
        max_items=input_model.maxPostCount,
        include_nsfw=input_model.includeNSFW,
        date_limit=input_model.postDateLimit,
    ):
        item = _emit(parse_post(data), include_nsfw=input_model.includeNSFW)
        if item is not None:
            yield item
        # Collect ids now; fetch the comment trees in parallel below. Walking
        # them here would serialize one .json per post on this single sticky IP.
        parsed_id = data.get("id")
        if not input_model.skipComments and isinstance(parsed_id, str):
            post_ids.append(parsed_id)

    if post_ids:
        comment_jobs = [
            _post_flow(
                pid,
                input_model=input_model,
                subreddit=subreddit,
                include_post=False,
            )
            for pid in post_ids
        ]
        async for comment in fan_out(comment_jobs, concurrency=_COMMENT_CONCURRENCY):
            yield comment


async def _user_flow(
    username: str,
    *,
    input_model: RedditScrapeInput,
    content: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Page a user's overview/submitted/comments listing (mixed t3 + t1)."""
    if content == "submitted":
        path, kinds = f"user/{username}/submitted", frozenset({"t3"})
    elif content == "comments":
        path, kinds = f"user/{username}/comments", frozenset({"t1"})
    else:
        path = f"user/{username}"
        kinds = frozenset({"t1"} if input_model.skipUserPosts else {"t3", "t1"})

    async for data in _paginate_listing(
        path,
        {},
        kinds,
        max_items=input_model.maxItems,
        include_nsfw=input_model.includeNSFW,
        date_limit=input_model.postDateLimit,
    ):
        # A user listing mixes posts (t3) and comments (t1); a post has a title.
        parsed = parse_post(data) if data.get("title") is not None else parse_comment(
            data
        )
        item = _emit(parsed, include_nsfw=input_model.includeNSFW)
        if item is not None:
            yield item


async def _search_flow(
    query: str,
    *,
    input_model: RedditScrapeInput,
    subreddit: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Global search, or in-subreddit when ``subreddit`` is set. De-dupes by id."""
    params: dict[str, Any] = {"q": query, "sort": input_model.sort}
    if input_model.time:
        params["t"] = input_model.time
    if subreddit:
        path = f"r/{subreddit}/search"
        params["restrict_sr"] = "on"
    else:
        path = "search"

    seen: set[str] = set()
    async for data in _paginate_listing(
        path,
        params,
        frozenset({"t3"}),
        max_items=input_model.maxItems,
        include_nsfw=input_model.includeNSFW,
        date_limit=input_model.postDateLimit,
    ):
        post_id = data.get("id")
        if isinstance(post_id, str):
            if post_id in seen:
                continue
            seen.add(post_id)
        item = _emit(parse_post(data), include_nsfw=input_model.includeNSFW)
        if item is not None:
            yield item


def _dispatch(
    resolved: ResolvedUrl, input_model: RedditScrapeInput
) -> AsyncIterator[dict[str, Any]]:
    """Route a resolved URL to its flow (returns the flow's async generator)."""
    if resolved.kind == "post":
        return _post_flow(
            resolved.value, input_model=input_model, subreddit=resolved.subreddit
        )
    if resolved.kind == "subreddit":
        return _subreddit_flow(
            resolved.value, input_model=input_model, sort=resolved.sort
        )
    if resolved.kind == "user":
        return _user_flow(
            resolved.value, input_model=input_model, content=resolved.content
        )
    return _search_flow(
        resolved.value, input_model=input_model, subreddit=resolved.subreddit
    )


def _capped_targets(
    resolved: list[ResolvedUrl], input_model: RedditScrapeInput
) -> list[ResolvedUrl]:
    """Apply the target-count caps (``maxCommunitiesCount`` / ``maxUserCount``).

    These bound how many subreddit / user *targets* are scraped; per-target item
    counts are bounded inside each flow (maxPostCount / maxItems / maxComments).
    """
    subs = users = 0
    out: list[ResolvedUrl] = []
    for r in resolved:
        if r.kind == "subreddit":
            if subs >= input_model.maxCommunitiesCount:
                continue
            subs += 1
        elif r.kind == "user":
            if users >= input_model.maxUserCount:
                continue
            users += 1
        out.append(r)
    return out


async def iter_reddit(
    input_model: RedditScrapeInput,
) -> AsyncIterator[dict[str, Any]]:
    """Yield flat Reddit items. ``startUrls`` override ``searches``.

    Independent targets fan out concurrently; each target's ``after`` paging
    stays sequential.
    """
    if input_model.startUrls:
        resolved: list[ResolvedUrl] = []
        for entry in input_model.startUrls:
            r = resolve_url(entry.url)
            if r is None:
                logger.warning("[reddit] unrecognized URL: %s", entry.url)
                continue
            resolved.append(r)
        jobs = [
            _dispatch(r, input_model)
            for r in _capped_targets(resolved, input_model)
        ]
        async for item in fan_out(jobs):
            yield item
        return

    jobs = [
        _search_flow(
            query,
            input_model=input_model,
            subreddit=input_model.searchCommunityName,
        )
        for query in input_model.searches
    ]
    async for item in fan_out(jobs):
        yield item


async def scrape_reddit(
    input_model: RedditScrapeInput, *, limit: int | None = None
) -> list[dict[str, Any]]:
    """Collect :func:`iter_reddit` into a list, honoring an optional ``limit``.

    ``limit`` is a request-time policy guard, NOT a ceiling in the streaming
    core.
    """
    results: list[dict[str, Any]] = []
    async for item in iter_reddit(input_model):
        results.append(item)
        if limit is not None and len(results) >= limit:
            break
    return results
