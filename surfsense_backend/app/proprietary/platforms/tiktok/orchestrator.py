"""Resolve a :class:`TikTokScrapeInput` into targets and stream their items.

Targets run sequentially on one warm sticky IP; ``limit`` is collector policy
applied by :func:`scrape_tiktok`, never baked into a flow. Each kind routes to
its flow via :func:`_dispatch`.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import quote

from .flows import FetchFn
from .flows.video import iter_video
from .schemas import TikTokScrapeInput
from .session import fetch_html, proxy_session
from .targets import resolve_target
from .targets.types import TikTokTarget

logger = logging.getLogger(__name__)

_PROFILE_URL = "https://www.tiktok.com/@{name}"
_HASHTAG_URL = "https://www.tiktok.com/tag/{tag}"
_SEARCH_URL = "https://www.tiktok.com/search?q={query}"


async def _empty() -> AsyncIterator[dict[str, Any]]:
    for _ in ():
        yield {}


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


def _dispatch(target: TikTokTarget, *, fetch: FetchFn) -> AsyncIterator[dict[str, Any]]:
    if target.kind == "video":
        return iter_video(target, fetch=fetch)
    # Listings come from the signed item_list API, not the blob.
    logger.debug("[tiktok] no blob flow for %s target", target.kind)
    return _empty()


async def iter_tiktok(
    input_model: TikTokScrapeInput, *, fetch: FetchFn = fetch_html
) -> AsyncIterator[dict[str, Any]]:
    """Yield normalized items for every resolved target, in order."""
    async with proxy_session():
        for target in _resolve_targets(input_model):
            async for item in _dispatch(target, fetch=fetch):
                yield item


async def scrape_tiktok(
    input_model: TikTokScrapeInput,
    *,
    limit: int | None = None,
    fetch: FetchFn = fetch_html,
) -> list[dict[str, Any]]:
    """Collect :func:`iter_tiktok` into a list, honoring an optional ``limit``."""
    from app.capabilities.core.progress import emit_progress

    results: list[dict[str, Any]] = []
    async for item in iter_tiktok(input_model, fetch=fetch):
        results.append(item)
        emit_progress("scraping", current=len(results), total=limit, unit="item")
        if limit is not None and len(results) >= limit:
            break
    return results
