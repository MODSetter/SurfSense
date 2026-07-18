"""Executor for the ``amazon.scrape`` capability."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from urllib.parse import quote_plus

from app.capabilities.amazon.scrape.schemas import (
    MAX_AMAZON_RESULTS,
    ScrapeInput,
    ScrapeOutput,
)
from app.capabilities.core import Executor
from app.capabilities.core.progress import emit_progress
from app.proprietary.platforms.amazon import AmazonScrapeInput, scrape_products

ScrapeFn = Callable[..., Awaitable[list[dict]]]


def build_scrape_executor(scrape_fn: ScrapeFn | None = None) -> Executor:
    """Bind the capability input mapping to a replaceable scraper function."""
    scrape_fn = scrape_fn or scrape_products

    async def execute(payload: ScrapeInput) -> ScrapeOutput:
        search_urls = [
            f"https://{payload.domain}/s?k={quote_plus(term)}"
            for term in payload.search_terms
        ]
        input_model = AmazonScrapeInput(
            categoryOrProductUrls=[
                {"url": url} for url in [*payload.urls, *search_urls]
            ],
            maxItemsPerStartUrl=payload.max_items,
            language=payload.language,
            countryCode=payload.country_code,
            zipCode=payload.zip_code,
            scrapeProductDetails=payload.include_details,
            maxOffers=payload.max_offers,
            scrapeSellers=payload.include_sellers,
            maxProductVariantsAsSeparateResults=payload.max_variants,
            scrapeProductVariantPrices=payload.include_variant_prices,
        )
        emit_progress(
            "starting",
            "Scraping Amazon products",
            total=payload.estimated_units,
            unit="product",
        )
        items = await scrape_fn(input_model, limit=MAX_AMAZON_RESULTS)
        emit_progress(
            "done",
            f"Scraped {sum('error' not in item for item in items)} product(s)",
            current=len(items),
            total=payload.estimated_units,
            unit="product",
        )
        return ScrapeOutput(items=items)

    return execute
