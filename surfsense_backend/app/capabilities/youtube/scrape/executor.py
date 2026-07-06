"""``youtube.scrape`` executor: verb input → scraper → video items."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.capabilities.core import Executor
from app.capabilities.core.progress import emit_progress
from app.capabilities.youtube.scrape.schemas import ScrapeInput, ScrapeOutput
from app.proprietary.platforms.youtube import (
    YouTubeScrapeInput,
    scrape_youtube,
)

ScrapeFn = Callable[[YouTubeScrapeInput], Awaitable[list[dict]]]


def build_scrape_executor(scrape_fn: ScrapeFn | None = None) -> Executor:
    """Bind the executor to a scraper fn (defaults to the proprietary actor)."""
    scrape_fn = scrape_fn or scrape_youtube

    async def execute(payload: ScrapeInput) -> ScrapeOutput:
        # Channels emit three content types; cap each at the caller's max_results
        # so a channel scrape isn't silently limited to plain videos only.
        actor_input = YouTubeScrapeInput(
            startUrls=[{"url": url} for url in payload.urls],
            searchQueries=payload.search_queries,
            maxResults=payload.max_results,
            maxResultsShorts=payload.max_results,
            maxResultStreams=payload.max_results,
            downloadSubtitles=payload.download_subtitles,
            subtitlesLanguage=payload.subtitles_language,
        )
        emit_progress("starting", "Resolving YouTube targets", total=payload.max_results, unit="video")
        items = await scrape_fn(actor_input)
        emit_progress("done", f"Scraped {len(items)} video(s)", current=len(items), unit="video")
        return ScrapeOutput(items=items)

    return execute
