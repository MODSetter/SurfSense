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

from .flows import FetchFn, FetchListingFn, FetchUsersFn
from .flows.listing import iter_listing
from .flows.profile import iter_profile
from .flows.user_search import iter_user_search
from .flows.video import iter_video
from .schemas import TikTokScrapeInput
from .session import fetch_html, fetch_item_list, fetch_user_search
from .targets import resolve_target
from .targets.types import TikTokTarget

_PROFILE_URL = "https://www.tiktok.com/@{name}"
_HASHTAG_URL = "https://www.tiktok.com/tag/{tag}"
_SEARCH_URL = "https://www.tiktok.com/search?q={query}"


def _resolve_targets(input_model: TikTokScrapeInput) -> list[TikTokTarget]:
    """Build the target list from every input source, dropping unresolved URLs."""
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
        targets.append(
            TikTokTarget("search", query, _SEARCH_URL.format(query=quote(query)))
        )
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


async def iter_tiktok(
    input_model: TikTokScrapeInput,
    *,
    fetch: FetchFn = fetch_html,
    fetch_listing: FetchListingFn = fetch_item_list,
) -> AsyncIterator[dict[str, Any]]:
    """Yield normalized items for every resolved target, in order.

    The video flow's ``fetch_html`` opens its own warmed proxy session per call
    when none is bound; the listing flow drives its own browser. Neither binds a
    ContextVar across these ``yield``s, so the generator stays context-safe.
    """
    cap = input_model.resultsPerPage
    for target in _resolve_targets(input_model):
        async for item in _dispatch(
            target, cap=cap, fetch=fetch, fetch_listing=fetch_listing
        ):
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
