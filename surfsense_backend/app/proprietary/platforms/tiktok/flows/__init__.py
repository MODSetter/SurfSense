"""Per-target scrape flows: resolved target -> normalized items."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable

FetchFn = Callable[[str], Awaitable[str | None]]
"""Fetch a page's HTML by URL (blob-first video flow)."""

FetchListingFn = Callable[[str, int], Awaitable[list[dict]]]
"""Load a listing page and return up to ``count`` captured itemStructs."""

FetchUsersFn = Callable[[str, int], Awaitable[list[dict]]]
"""Load a user-search page and return up to ``count`` captured ``user_info`` records."""

FetchCommentsFn = Callable[[str, int], Awaitable[list[dict]]]
"""Load a video page and return up to ``count`` captured raw comment records."""

FlowResult = AsyncIterator[dict]
