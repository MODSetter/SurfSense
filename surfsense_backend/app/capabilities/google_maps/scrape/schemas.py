"""``google_maps.scrape`` I/O contracts.

A lean, agent-friendly surface over ``GoogleMapsScrapeInput``
(``app/proprietary/platforms/google_maps``). The executor maps this to the full
scraper input; the scraper's ``PlaceItem`` is reused verbatim as the output
element.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from app.proprietary.platforms.google_maps import PlaceItem

MAX_MAPS_SOURCES = 20
"""Per-call cap on queries + urls + place_ids: bounds a sync request's fan-out."""


class ScrapeInput(BaseModel):
    search_queries: list[str] = Field(
        default_factory=list,
        max_length=MAX_MAPS_SOURCES,
        description=(
            "Google Maps search terms (e.g. 'coffee shops', 'dentist'); each "
            "returns up to max_places. Provide these OR urls OR place_ids "
            "(at least one is required). Pair with location to scope a search."
        ),
    )
    urls: list[str] = Field(
        default_factory=list,
        max_length=MAX_MAPS_SOURCES,
        description=(
            "Google Maps URLs — a place page (/maps/place/...) or a search "
            "results URL. Provide these OR search_queries OR place_ids."
        ),
    )
    place_ids: list[str] = Field(
        default_factory=list,
        max_length=MAX_MAPS_SOURCES,
        description=(
            "Known Google place IDs (ChIJ...) to fetch directly. Provide these "
            "OR search_queries OR urls."
        ),
    )
    location: str | None = Field(
        default=None,
        description="Location to scope search_queries to, e.g. 'New York, USA'.",
    )
    max_places: int = Field(
        default=10,
        ge=1,
        le=1000,
        description="Max places to return per search query.",
    )
    language: str = Field(
        default="en",
        description="Result language code, e.g. 'en', 'fr'.",
    )
    include_details: bool = Field(
        default=False,
        description=(
            "Also fetch each place's detail page — opening hours, popular "
            "times, extra contact info (slower; more requests)."
        ),
    )
    max_reviews: int = Field(
        default=0,
        ge=0,
        le=100_000,
        description="Reviews to attach per place (0 = none).",
    )
    max_images: int = Field(
        default=0,
        ge=0,
        description="Images to attach per place (0 = none).",
    )

    @model_validator(mode="after")
    def _require_a_source(self) -> ScrapeInput:
        if not (self.search_queries or self.urls or self.place_ids):
            raise ValueError(
                "Provide at least one of 'search_queries', 'urls', or 'place_ids'."
            )
        return self

    @property
    def estimated_units(self) -> int:
        """Worst-case billable places: each search query yields up to
        ``max_places``; direct URLs and place_ids yield one each."""
        return (
            len(self.search_queries) * self.max_places
            + len(self.urls)
            + len(self.place_ids)
        )

    @property
    def estimated_review_units(self) -> int:
        """Worst-case attached reviews for the dual-meter gate: up to
        ``max_reviews`` per place across the worst-case place fan-out."""
        return self.estimated_units * self.max_reviews


class ScrapeOutput(BaseModel):
    items: list[PlaceItem] = Field(
        default_factory=list,
        description="One place item per result, in the scraper's emission order.",
    )

    @property
    def billable_units(self) -> int:
        """One returned place = one billable place unit."""
        return len(self.items)

    @property
    def attached_review_count(self) -> int:
        """Reviews attached inline across all places — the second (review)
        meter for this dual-metered verb (populated only when max_reviews > 0)."""
        return sum(len(item.reviews) for item in self.items)
