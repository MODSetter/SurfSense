"""``instagram.details`` executor: verb input → scraper → detail items."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.capabilities.core import Executor
from app.capabilities.core.progress import emit_progress
from app.capabilities.instagram.details.schemas import DetailsInput, DetailsOutput
from app.exceptions import ForbiddenError
from app.proprietary.platforms.instagram import (
    InstagramAccessBlockedError,
    InstagramScrapeInput,
    scrape_instagram,
)

ScrapeFn = Callable[..., Awaitable[list[dict]]]


def build_details_executor(scrape_fn: ScrapeFn | None = None) -> Executor:
    """Bind the executor to a scraper fn (defaults to the proprietary actor)."""
    scrape_fn = scrape_fn or scrape_instagram

    async def execute(payload: DetailsInput) -> DetailsOutput:
        actor_input = InstagramScrapeInput(
            resultsType="details",
            directUrls=payload.urls,
            search=",".join(payload.search_queries),
            searchType=payload.search_type,
            searchLimit=payload.search_limit,
        )
        emit_progress(
            "starting",
            "Resolving Instagram detail targets",
            total=payload.max_items,
            unit="item",
        )
        try:
            items = await scrape_fn(actor_input, limit=payload.max_items)
        except InstagramAccessBlockedError as exc:
            raise ForbiddenError(
                f"Instagram refused anonymous access: {exc}",
                code="INSTAGRAM_ACCESS_BLOCKED",
            ) from exc
        emit_progress(
            "done", f"Scraped {len(items)} item(s)", current=len(items), unit="item"
        )
        return DetailsOutput(items=items)

    return execute
