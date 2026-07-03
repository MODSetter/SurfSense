"""``google_maps.scrape`` executor: verb input → scraper → place items."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.capabilities.core import Executor
from app.capabilities.google_maps.scrape.schemas import ScrapeInput, ScrapeOutput
from app.exceptions import ForbiddenError
from app.proprietary.platforms.google_maps import (
    GoogleMapsScrapeInput,
    scrape_places,
)
from app.proprietary.platforms.google_maps.scraper import SignInRequiredError

ScrapeFn = Callable[[GoogleMapsScrapeInput], Awaitable[list[dict]]]


def build_scrape_executor(scrape_fn: ScrapeFn | None = None) -> Executor:
    """Bind the executor to a scraper fn (defaults to the proprietary actor)."""
    scrape_fn = scrape_fn or scrape_places

    async def execute(payload: ScrapeInput) -> ScrapeOutput:
        actor_input = GoogleMapsScrapeInput(
            searchStringsArray=payload.search_queries,
            startUrls=[{"url": url} for url in payload.urls],
            placeIds=payload.place_ids,
            locationQuery=payload.location,
            maxCrawledPlacesPerSearch=payload.max_places,
            language=payload.language,
            scrapePlaceDetailPage=payload.include_details,
            maxReviews=payload.max_reviews,
            maxImages=payload.max_images,
        )
        try:
            items = await scrape_fn(actor_input)
        except SignInRequiredError as exc:
            raise ForbiddenError(
                f"Google sign in required: {exc}", code="GOOGLE_SIGNIN_REQUIRED"
            ) from exc
        return ScrapeOutput(items=items)

    return execute
