"""Resolve a :class:`TikTokScrapeInput` into targets and stream their items.

Targets, user-search queries and the comments of several videos run
concurrently, each worker on its own keep-alive exit, and still come out in
input order; at most two browser targets load at once per call. ``limit`` is
collector policy applied by :func:`scrape_tiktok`, never baked into a flow; once
it is reached the targets still running are cancelled. Each kind routes to its flow
via :func:`_dispatch`: video URLs read the rehydration blob over HTTP, listings
capture signed item_list XHRs through the stealth browser.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import aclosing
from typing import Any
from urllib.parse import quote

from proprietary.scraping.concurrency import ordered_map

from .extraction.timestamps import now_iso
from .flows import FetchCommentsFn, FetchFn, FetchListingFn, FetchUsersFn
from .flows.comments import iter_comments
from .flows.listing import iter_listing
from .flows.profile import iter_profile
from .flows.user_search import iter_user_search
from .flows.video import iter_video
from .schemas import ErrorItem, TikTokScrapeInput
from .session import (
    fetch_comments,
    fetch_html,
    fetch_item_list,
    fetch_trending,
    fetch_user_search,
    proxy_session,
)
from .session.listing import BROWSER_SLOTS
from .targets import resolve_target
from .targets.types import TikTokTarget

OnItem = Callable[[int], Awaitable[None]]
"""Hears the running item count after each item, for the caller's progress."""

_PROFILE_URL = "https://www.tiktok.com/@{name}"
_HASHTAG_URL = "https://www.tiktok.com/tag/{tag}"
_SEARCH_URL = "https://www.tiktok.com/search?q={query}"
_EXPLORE_URL = "https://www.tiktok.com/explore"
# Video pages and comment threads fetched at once per call: plain HTTP GETs, each
# worker on its own exit, so 3 videos cost about one.
_HTTP_CONCURRENCY = 4
# Browser targets (profiles, hashtags, searches, user-search queries) loading at
# once per call, each on its own exit; TIKTOK_BROWSER_CONCURRENCY=1 runs them one
# after another again.
_BROWSER_CONCURRENCY = max(1, int(os.getenv("TIKTOK_BROWSER_CONCURRENCY", "2")))


def _workers(concurrency: int, limit: int | None) -> int:
    """``concurrency``, but no more targets at once than ``limit`` can use.

    Every target yields at least one item (an ErrorItem when nothing loads), so
    more than ``limit`` in flight only spends requests the collector drops.
    """
    return concurrency if limit is None else max(1, min(concurrency, limit))


def _resolve_targets(input_model: TikTokScrapeInput) -> list[TikTokTarget]:
    """Build the target list from every input source.

    ``searchQueries`` map to the same ``tiktok.com/search?q=`` targets that a raw
    search URL in ``startUrls``/``postURLs`` resolves to, so both share the
    listing flow's parse/dedupe/cap/empty-ErrorItem contract (the anonymous
    search feed often withholds results, degrading to one honest ErrorItem rather
    than a silent empty).
    """
    targets: list[TikTokTarget] = []
    for entry in input_model.startUrls:
        resolved = resolve_target(entry.url)
        if resolved is not None:
            targets.append(resolved)
    for url in input_model.postURLs:
        resolved = resolve_target(url)
        if resolved is not None:
            targets.append(resolved)
    for profile in input_model.profiles:
        name = profile.lstrip("@")
        targets.append(TikTokTarget("profile", name, _PROFILE_URL.format(name=name)))
    for tag in input_model.hashtags:
        targets.append(TikTokTarget("hashtag", tag, _HASHTAG_URL.format(tag=tag)))
    for query in input_model.searchQueries:
        resolved = resolve_target(_SEARCH_URL.format(query=quote(query)))
        if resolved is not None:
            targets.append(resolved)
    return targets


def _dispatch(
    target: TikTokTarget,
    *,
    cap: int,
    fetch: FetchFn,
    fetch_listing: FetchListingFn,
) -> AsyncIterator[dict[str, Any]]:
    if target.kind == "video":
        return iter_video(target, fetch=fetch)
    if target.kind == "profile":
        return iter_profile(target, cap=cap, fetch=fetch, fetch_listing=fetch_listing)
    return iter_listing(target, cap=cap, fetch_listing=fetch_listing)


async def _collected(items: AsyncIterator[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item async for item in items]


async def iter_tiktok(
    input_model: TikTokScrapeInput,
    *,
    fetch: FetchFn = fetch_html,
    fetch_listing: FetchListingFn = fetch_item_list,
    limit: int | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Yield normalized items for every resolved target, in order.

    Targets run concurrently, each ``ordered_map`` worker binding its own proxy
    session in its own task; browser targets also wait for one of
    ``_BROWSER_CONCURRENCY`` slots. ``limit`` is only a hint that caps how many
    targets run at once. Nothing binds a ContextVar across these ``yield``s, so
    the generator stays context-safe.
    """
    cap = input_model.resultsPerPage
    browsers = asyncio.Semaphore(_BROWSER_CONCURRENCY)

    async def run(target: TikTokTarget) -> list[dict[str, Any]]:
        items = _dispatch(target, cap=cap, fetch=fetch, fetch_listing=fetch_listing)
        if target.kind == "video":
            return await _collected(items)
        async with browsers:
            return await _collected(items)

    targets = ordered_map(
        _resolve_targets(input_model),
        run,
        concurrency=_workers(_HTTP_CONCURRENCY, limit),
        worker_context=proxy_session,
    )
    async with aclosing(targets) as runs:
        async for items in runs:
            for item in items:
                yield item


async def scrape_tiktok(
    input_model: TikTokScrapeInput,
    *,
    limit: int | None = None,
    fetch: FetchFn = fetch_html,
    fetch_listing: FetchListingFn = fetch_item_list,
    on_item: OnItem | None = None,
) -> list[dict[str, Any]]:
    """Collect :func:`iter_tiktok` into a list, honoring an optional ``limit``."""
    results: list[dict[str, Any]] = []
    # aclosing: stopping at the limit cancels the targets still running.
    stream = iter_tiktok(
        input_model, fetch=fetch, fetch_listing=fetch_listing, limit=limit
    )
    async with aclosing(stream) as items:
        async for item in items:
            results.append(item)
            if on_item is not None:
                await on_item(len(results))
            if limit is not None and len(results) >= limit:
                break
    return results


async def search_tiktok_users(
    queries: list[str],
    *,
    per_query: int,
    limit: int | None = None,
    fetch_users: FetchUsersFn = fetch_user_search,
    on_item: OnItem | None = None,
) -> list[dict[str, Any]]:
    """Collect user-search account records across queries, honoring ``limit``.

    Queries load concurrently (``_BROWSER_CONCURRENCY`` at once), in input order.
    """
    results: list[dict[str, Any]] = []
    searches = ordered_map(
        queries,
        lambda query: _collected(
            iter_user_search(query, cap=per_query, fetch_users=fetch_users)
        ),
        concurrency=_workers(_BROWSER_CONCURRENCY, limit),
    )
    async with aclosing(searches) as runs:
        async for items in runs:
            for item in items:
                results.append(item)
                if on_item is not None:
                    await on_item(len(results))
                if limit is not None and len(results) >= limit:
                    return results
    return results


async def scrape_tiktok_trending(
    *,
    count: int,
    fetch_trending_fn: FetchListingFn = fetch_trending,
    on_item: OnItem | None = None,
) -> list[dict[str, Any]]:
    """Collect up to ``count`` trending videos from the Explore feed.

    A single global feed, so it reuses the listing flow (parse/dedupe/cap/empty-
    ErrorItem) over a synthetic target — no user input to resolve.
    """
    target = TikTokTarget(kind="trending", value="explore", url=_EXPLORE_URL)
    results: list[dict[str, Any]] = []
    async for item in iter_listing(target, cap=count, fetch_listing=fetch_trending_fn):
        results.append(item)
        if on_item is not None:
            await on_item(len(results))
    return results


async def scrape_tiktok_comments(
    video_urls: list[str],
    *,
    per_video: int,
    limit: int | None = None,
    fetch_comments_fn: FetchCommentsFn = fetch_comments,
    on_item: OnItem | None = None,
) -> list[dict[str, Any]]:
    """Collect comments across video URLs, honoring ``limit``.

    Videos are fetched concurrently and their comments kept in input order; at
    most ``_BROWSER_CONCURRENCY`` threads fall back to the browser at once. A
    non-video URL yields one ``bad_url`` ErrorItem (never a silent drop) so the
    caller can tell "wrong input" from "video has no comments".
    """

    async def one_video(url: str) -> list[dict[str, Any]]:
        target = resolve_target(url)
        if target is None or target.kind != "video":
            return [
                ErrorItem(
                    url=url,
                    input=url,
                    error="Not a TikTok video URL.",
                    errorCode="bad_url",
                    scrapedAt=now_iso(),
                ).to_output()
            ]
        return await _collected(
            iter_comments(target, cap=per_video, fetch_comments=fetch_comments_fn)
        )

    results: list[dict[str, Any]] = []
    # Bound before the workers start, so each task copies it.
    slots = BROWSER_SLOTS.set(asyncio.Semaphore(_BROWSER_CONCURRENCY))
    try:
        threads = ordered_map(
            video_urls,
            one_video,
            concurrency=_workers(_HTTP_CONCURRENCY, limit),
            worker_context=proxy_session,
        )
        async with aclosing(threads) as runs:
            async for items in runs:
                for item in items:
                    results.append(item)
                    if on_item is not None:
                        await on_item(len(results))
                    if limit is not None and len(results) >= limit:
                        return results
    finally:
        BROWSER_SLOTS.reset(slots)
    return results
