"""Executor for the ``walmart.scrape`` capability."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.capabilities.core import Executor
from app.capabilities.core.progress import emit_progress
from app.capabilities.walmart.scrape.schemas import (
    MAX_WALMART_RESULTS,
    ScrapeInput,
    ScrapeOutput,
)
from app.proprietary.platforms.walmart import WalmartScrapeInput, scrape_products

ScrapeFn = Callable[..., Awaitable[list[dict]]]


def build_scrape_executor(scrape_fn: ScrapeFn | None = None) -> Executor:
    """Bind the capability input mapping to a replaceable scraper function."""
    scrape_fn = scrape_fn or scrape_products

    async def execute(payload: ScrapeInput) -> ScrapeOutput:
        input_model = WalmartScrapeInput(
            startUrls=payload.start_urls(),
            maxItemsPerStartUrl=payload.max_items,
            includeDetails=payload.include_details,
            includeReviewsSample=payload.include_reviews_sample,
        )
        emit_progress(
            "starting",
            "Scraping Walmart products",
            total=payload.estimated_units,
            unit="product",
        )
        items = await scrape_fn(input_model, limit=MAX_WALMART_RESULTS)
        emit_progress(
            "done",
            f"Scraped {sum('error' not in item for item in items)} product(s)",
            current=len(items),
            total=payload.estimated_units,
            unit="product",
        )
        return ScrapeOutput(items=items)

    return execute
