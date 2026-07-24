"""``tiktok.trending`` executor: Explore feed -> scraper -> TikTok video items."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.capabilities.core import Executor
from app.capabilities.core.progress import emit_progress
from app.capabilities.tiktok.trending.schemas import TrendingInput, TrendingOutput
from app.proprietary.platforms.tiktok import scrape_tiktok_trending

TrendingFn = Callable[..., Awaitable[list[dict]]]


def build_trending_executor(trending_fn: TrendingFn | None = None) -> Executor:
    """Bind the executor to a trending fn (defaults to the proprietary actor)."""
    trending_fn = trending_fn or scrape_tiktok_trending

    async def execute(payload: TrendingInput) -> TrendingOutput:
        emit_progress(
            "starting",
            "Fetching TikTok trending videos",
            total=payload.max_items,
            unit="item",
        )
        items = await trending_fn(count=payload.max_items)
        emit_progress(
            "done", f"Fetched {len(items)} video(s)", current=len(items), unit="item"
        )
        return TrendingOutput(items=items)

    return execute
