"""``tiktok.scrape`` executor: verb input → scraper → TikTok video items."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.capabilities.core import Executor
from app.capabilities.core.progress import emit_progress
from app.capabilities.tiktok.scrape.schemas import ScrapeInput, ScrapeOutput
from app.exceptions import ForbiddenError
from app.proprietary.platforms.tiktok import (
    TikTokAccessBlockedError,
    TikTokScrapeInput,
    scrape_tiktok,
)

ScrapeFn = Callable[..., Awaitable[list[dict]]]


def build_scrape_executor(scrape_fn: ScrapeFn | None = None) -> Executor:
    """Bind the executor to a scraper fn (defaults to the proprietary actor)."""
    scrape_fn = scrape_fn or scrape_tiktok

    async def execute(payload: ScrapeInput) -> ScrapeOutput:
        actor_input = TikTokScrapeInput(
            startUrls=[{"url": url} for url in payload.urls],
            profiles=payload.profiles,
            hashtags=payload.hashtags,
            resultsPerPage=payload.results_per_page,
        )
        emit_progress(
            "starting", "Resolving TikTok targets", total=payload.max_items, unit="item"
        )
        try:
            items = await scrape_fn(actor_input, limit=payload.max_items)
        except TikTokAccessBlockedError as exc:
            # Anonymous-only scraper; a hard block can't be retried with creds.
            raise ForbiddenError(
                f"TikTok refused anonymous access: {exc}",
                code="TIKTOK_ACCESS_BLOCKED",
            ) from exc
        emit_progress(
            "done", f"Scraped {len(items)} item(s)", current=len(items), unit="item"
        )
        return ScrapeOutput(items=items)

    return execute
