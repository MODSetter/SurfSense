"""``walmart.reviews`` I/O contracts.

A lean surface over ``WalmartReviewsInput``; the scraper's ``ReviewItem`` is
reused verbatim as the output element. Accepts product URLs or bare item ids —
both resolve to a ``usItemId`` the reviews page is keyed on.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.proprietary.platforms.walmart import ReviewItem

MAX_WALMART_REVIEW_SOURCES = 20


class ReviewsInput(BaseModel):
    urls: list[str] = Field(
        default_factory=list,
        max_length=MAX_WALMART_REVIEW_SOURCES,
        description=(
            "Walmart product URLs (/ip/...) or reviews URLs to fetch reviews for. "
            "Provide these OR item_ids (at least one is required)."
        ),
    )
    item_ids: list[str] = Field(
        default_factory=list,
        max_length=MAX_WALMART_REVIEW_SOURCES,
        description="Walmart numeric item ids (usItemId) to fetch reviews for.",
    )
    max_reviews: int = Field(
        default=200,
        ge=1,
        le=5000,
        description="Max reviews to return per product (10 per page).",
    )
    sort_by: Literal["most-recent", "most-helpful", "rating-high", "rating-low"] = (
        Field(default="most-recent", description="Review ordering.")
    )

    @model_validator(mode="after")
    def _require_a_source(self) -> ReviewsInput:
        if not (self.urls or self.item_ids):
            raise ValueError("Provide at least one of 'urls' or 'item_ids'.")
        return self

    def sources(self) -> list[str]:
        """URLs and item ids merged; the scraper resolves each to a usItemId."""
        return [*self.urls, *self.item_ids]

    @property
    def estimated_units(self) -> int:
        """Worst-case billable reviews: up to ``max_reviews`` per source."""
        return (len(self.urls) + len(self.item_ids)) * self.max_reviews


class ReviewsOutput(BaseModel):
    items: list[ReviewItem] = Field(
        default_factory=list,
        description="One item per review, in the scraper's emission order.",
    )

    @property
    def billable_units(self) -> int:
        """One returned review = one billable unit; error items are not billed."""
        return sum(
            1
            for item in self.items
            if not (item.model_extra and item.model_extra.get("error"))
        )
