"""``google_maps.reviews`` I/O contracts.

A lean surface over ``GoogleMapsReviewsInput``; the scraper's ``ReviewItem`` is
reused verbatim as the output element.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.proprietary.platforms.google_maps import ReviewItem

MAX_MAPS_REVIEW_SOURCES = 20
"""Per-call cap on urls + place_ids: bounds how many places one request harvests."""


class ReviewsInput(BaseModel):
    urls: list[str] = Field(
        default_factory=list,
        max_length=MAX_MAPS_REVIEW_SOURCES,
        description=(
            "Google Maps place URLs to fetch reviews for. Provide these OR "
            "place_ids (at least one is required)."
        ),
    )
    place_ids: list[str] = Field(
        default_factory=list,
        max_length=MAX_MAPS_REVIEW_SOURCES,
        description=(
            "Known Google place IDs (ChIJ...) to fetch reviews for. Provide "
            "these OR urls."
        ),
    )
    max_reviews: int = Field(
        default=20,
        ge=1,
        le=100_000,
        description="Max reviews to return per place.",
    )
    sort_by: Literal["newest", "mostRelevant", "highestRanking", "lowestRanking"] = (
        Field(
            default="newest",
            description="Review ordering.",
        )
    )
    language: str = Field(
        default="en",
        description="Review language code, e.g. 'en', 'fr'.",
    )
    start_date: str | None = Field(
        default=None,
        description="Only reviews on/after this ISO date, e.g. '2024-01-01'.",
    )

    @model_validator(mode="after")
    def _require_a_source(self) -> ReviewsInput:
        if not (self.urls or self.place_ids):
            raise ValueError("Provide at least one of 'urls' or 'place_ids'.")
        return self


class ReviewsOutput(BaseModel):
    items: list[ReviewItem] = Field(
        default_factory=list,
        description="One item per review, in the scraper's emission order.",
    )
