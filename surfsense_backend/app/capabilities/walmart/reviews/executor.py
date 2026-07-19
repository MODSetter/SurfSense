"""``walmart.reviews`` executor: verb input → scraper → review items."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.capabilities.core import Executor
from app.capabilities.core.progress import emit_progress
from app.capabilities.walmart.reviews.schemas import ReviewsInput, ReviewsOutput
from app.proprietary.platforms.walmart import WalmartReviewsInput, scrape_reviews

ReviewsFn = Callable[..., Awaitable[list[dict]]]


def build_reviews_executor(scrape_fn: ReviewsFn | None = None) -> Executor:
    """Bind the executor to a reviews scraper fn (defaults to the proprietary actor)."""
    scrape_fn = scrape_fn or scrape_reviews

    async def execute(payload: ReviewsInput) -> ReviewsOutput:
        input_model = WalmartReviewsInput(
            itemIds=payload.sources(),
            maxReviews=payload.max_reviews,
            sort=payload.sort_by,
        )
        emit_progress(
            "starting",
            "Fetching Walmart reviews",
            total=payload.estimated_units,
            unit="review",
        )
        items = await scrape_fn(input_model, limit=payload.estimated_units)
        emit_progress(
            "done",
            f"Scraped {sum('error' not in item for item in items)} review(s)",
            current=len(items),
            unit="review",
        )
        return ReviewsOutput(items=items)

    return execute
