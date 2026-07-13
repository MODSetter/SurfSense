"""Resolve a :class:`TikTokScrapeInput` into targets and stream their items.

Targets run sequentially on one warm sticky IP; ``limit`` is collector policy
applied by :func:`scrape_tiktok`, never baked into a flow. Each kind routes to
its flow via :func:`_dispatch`: video URLs read the rehydration blob over HTTP,
listings capture signed item_list XHRs through the stealth browser.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import quote

from app.proprietary.platforms.google_search.schemas import GoogleSearchScrapeInput
from app.proprietary.platforms.google_search.scraper import scrape_serps

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
)
from .targets import resolve_target
from .targets.types import TikTokTarget

_PROFILE_URL = "https://www.tiktok.com/@{name}"
_HASHTAG_URL = "https://www.tiktok.com/tag/{tag}"
_SEARCH_URL = "https://www.tiktok.com/search?q={query}"
_EXPLORE_URL = "https://www.tiktok.com/explore"

# A ``searchQueries`` term whose Google discovery surfaced no scrapable video
# URLs degrades to one honest ErrorItem (mirrors the listing flow's contract:
# never vanish silently).
_EMPTY_DISCOVERY_MESSAGE = (
    "No public TikTok videos found for this query via Google discovery. Try a "
    "narrower phrasing, a hashtag, or a direct video URL."
)


def _resolve_targets(input_model: TikTokScrapeInput) -> list[TikTokTarget]:
    """Build the target list from the URL/profile/hashtag sources.

    ``searchQueries`` is deliberately excluded: TikTok's own keyword search is
    login-walled for anonymous sessions, so it is routed through Google video
    discovery in :func:`iter_tiktok` instead. A raw ``tiktok.com/search?...``
    URL passed explicitly in ``startUrls``/``postURLs`` still resolves here and
    keeps its native listing routing.
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
    return targets


async def _discover_via_google(query: str, *, limit: int) -> list[TikTokTarget]:
    """Discover public TikTok video targets via Google ``site:tiktok.com``.

    TikTok's anonymous keyword search is login-walled, so we reuse the existing
    ``google_search`` platform, classify each organic URL with ``resolve_target``,
    and keep only video hits (``/@user/video/<id>``) — the one kind that scrapes
    reliably over plain HTTP. Profile/hashtag/search/photo/non-tiktok results are
    dropped (accounts belong to the ``user_search`` verb). De-duped, capped at
    ``limit``.
    """
    serps = await scrape_serps(
        GoogleSearchScrapeInput(
            queries=query, site="tiktok.com", maxPagesPerQuery=1
        ),
        limit=1,
    )
    resolved: list[TikTokTarget] = []
    seen: set[str] = set()
    for serp in serps:
        for org in serp.get("organicResults") or []:
            url = org.get("url", "") if isinstance(org, dict) else ""
            target = resolve_target(url)
            if target is None or target.kind != "video":
                continue
            if target.value in seen:
                continue
            seen.add(target.value)
            resolved.append(target)
            if len(resolved) >= limit:
                return resolved
    return resolved


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


async def iter_tiktok(
    input_model: TikTokScrapeInput,
    *,
    fetch: FetchFn = fetch_html,
    fetch_listing: FetchListingFn = fetch_item_list,
) -> AsyncIterator[dict[str, Any]]:
    """Yield normalized items for every resolved target, in order.

    Direct sources (URLs, profiles, hashtags) resolve up front; ``searchQueries``
    then run through Google video discovery. The video flow's ``fetch_html``
    opens its own warmed proxy session per call when none is bound; the listing
    flow drives its own browser. Neither binds a ContextVar across these
    ``yield``s, so the generator stays context-safe.
    """
    cap = input_model.resultsPerPage
    for target in _resolve_targets(input_model):
        async for item in _dispatch(
            target, cap=cap, fetch=fetch, fetch_listing=fetch_listing
        ):
            yield item

    # searchQueries -> Google-discovered public video URLs, de-duped across
    # queries so the same video surfacing under two terms is scraped once.
    seen_videos: set[str] = set()
    for query in input_model.searchQueries:
        discovered = await _discover_via_google(query, limit=cap)
        if not discovered:
            yield ErrorItem(
                url=_SEARCH_URL.format(query=quote(query)),
                input=query,
                error=_EMPTY_DISCOVERY_MESSAGE,
                errorCode="no_items",
                scrapedAt=now_iso(),
            ).to_output()
            continue
        for target in discovered:
            if target.value in seen_videos:
                continue
            seen_videos.add(target.value)
            async for item in iter_video(target, fetch=fetch):
                yield item


async def scrape_tiktok(
    input_model: TikTokScrapeInput,
    *,
    limit: int | None = None,
    fetch: FetchFn = fetch_html,
    fetch_listing: FetchListingFn = fetch_item_list,
) -> list[dict[str, Any]]:
    """Collect :func:`iter_tiktok` into a list, honoring an optional ``limit``."""
    from app.capabilities.core.progress import emit_progress

    results: list[dict[str, Any]] = []
    async for item in iter_tiktok(input_model, fetch=fetch, fetch_listing=fetch_listing):
        results.append(item)
        emit_progress("scraping", current=len(results), total=limit, unit="item")
        if limit is not None and len(results) >= limit:
            break
    return results


async def search_tiktok_users(
    queries: list[str],
    *,
    per_query: int,
    limit: int | None = None,
    fetch_users: FetchUsersFn = fetch_user_search,
) -> list[dict[str, Any]]:
    """Collect user-search account records across queries, honoring ``limit``."""
    from app.capabilities.core.progress import emit_progress

    results: list[dict[str, Any]] = []
    for query in queries:
        async for item in iter_user_search(
            query, cap=per_query, fetch_users=fetch_users
        ):
            results.append(item)
            emit_progress("searching", current=len(results), total=limit, unit="item")
            if limit is not None and len(results) >= limit:
                return results
    return results


async def scrape_tiktok_trending(
    *,
    count: int,
    fetch_trending_fn: FetchListingFn = fetch_trending,
) -> list[dict[str, Any]]:
    """Collect up to ``count`` trending videos from the Explore feed.

    A single global feed, so it reuses the listing flow (parse/dedupe/cap/empty-
    ErrorItem) over a synthetic target — no user input to resolve.
    """
    from app.capabilities.core.progress import emit_progress

    target = TikTokTarget(kind="trending", value="explore", url=_EXPLORE_URL)
    results: list[dict[str, Any]] = []
    async for item in iter_listing(target, cap=count, fetch_listing=fetch_trending_fn):
        results.append(item)
        emit_progress("scraping", current=len(results), total=count, unit="item")
    return results


async def scrape_tiktok_comments(
    video_urls: list[str],
    *,
    per_video: int,
    limit: int | None = None,
    fetch_comments_fn: FetchCommentsFn = fetch_comments,
) -> list[dict[str, Any]]:
    """Collect comments across video URLs, honoring ``limit``.

    A non-video URL yields one ``bad_url`` ErrorItem (never a silent drop) so the
    caller can tell "wrong input" from "video has no comments".
    """
    from app.capabilities.core.progress import emit_progress

    results: list[dict[str, Any]] = []
    for url in video_urls:
        target = resolve_target(url)
        if target is None or target.kind != "video":
            results.append(
                ErrorItem(
                    url=url,
                    input=url,
                    error="Not a TikTok video URL.",
                    errorCode="bad_url",
                    scrapedAt=now_iso(),
                ).to_output()
            )
            emit_progress("scraping", current=len(results), total=limit, unit="item")
            if limit is not None and len(results) >= limit:
                return results
            continue
        async for item in iter_comments(
            target, cap=per_video, fetch_comments=fetch_comments_fn
        ):
            results.append(item)
            emit_progress("scraping", current=len(results), total=limit, unit="item")
            if limit is not None and len(results) >= limit:
                return results
    return results
