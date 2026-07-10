"""``tiktok.user_search`` executor: queries -> scraper -> TikTok profile items."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.capabilities.core import Executor
from app.capabilities.core.progress import emit_progress
from app.capabilities.tiktok.user_search.schemas import (
    UserSearchInput,
    UserSearchOutput,
)
from app.proprietary.platforms.tiktok import search_tiktok_users

SearchFn = Callable[..., Awaitable[list[dict]]]


def build_user_search_executor(search_fn: SearchFn | None = None) -> Executor:
    """Bind the executor to a search fn (defaults to the proprietary actor)."""
    search_fn = search_fn or search_tiktok_users

    async def execute(payload: UserSearchInput) -> UserSearchOutput:
        emit_progress(
            "starting",
            "Searching TikTok accounts",
            total=payload.max_items,
            unit="item",
        )
        items = await search_fn(
            payload.queries,
            per_query=payload.results_per_query,
            limit=payload.max_items,
        )
        emit_progress(
            "done", f"Found {len(items)} account(s)", current=len(items), unit="item"
        )
        return UserSearchOutput(items=items)

    return execute
