"""``google_maps.reviews`` executor: verb input → scraper → review items."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.capabilities.core import Executor
from app.capabilities.core.progress import emit_progress
from app.capabilities.google_maps.reviews.schemas import ReviewsInput, ReviewsOutput
from app.exceptions import ForbiddenError
from app.proprietary.platforms.google_maps import (
    GoogleMapsReviewsInput,
    scrape_reviews,
)
from app.proprietary.platforms.google_maps.scraper import SignInRequiredError

ReviewsFn = Callable[[GoogleMapsReviewsInput], Awaitable[list[dict]]]


def build_reviews_executor(scrape_fn: ReviewsFn | None = None) -> Executor:
    """Bind the executor to a reviews scraper fn (defaults to the proprietary actor)."""
    scrape_fn = scrape_fn or scrape_reviews

    async def execute(payload: ReviewsInput) -> ReviewsOutput:
        actor_input = GoogleMapsReviewsInput(
            startUrls=[{"url": url} for url in payload.urls],
            placeIds=payload.place_ids,
            maxReviews=payload.max_reviews,
            reviewsSort=payload.sort_by,
            reviewsStartDate=payload.start_date,
            language=payload.language,
        )
        emit_progress(
            "starting",
            "Fetching Google Maps reviews",
            total=payload.max_reviews,
            unit="review",
        )
        try:
            items = await scrape_fn(actor_input)
        except SignInRequiredError as exc:
            raise ForbiddenError(
                f"Google sign in required: {exc}", code="GOOGLE_SIGNIN_REQUIRED"
            ) from exc
        emit_progress(
            "done", f"Scraped {len(items)} review(s)", current=len(items), unit="review"
        )
        return ReviewsOutput(items=items)

    return execute
