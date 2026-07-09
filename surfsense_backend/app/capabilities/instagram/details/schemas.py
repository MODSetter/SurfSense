"""``instagram.details`` I/O contracts.

A lean surface over ``InstagramScrapeInput`` (``resultsType="details"``). Each
output item is a profile / hashtag / place, discriminated by the synthesized
``detailKind`` field (a SurfSense addition; every other field mirrors the actor).
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from app.capabilities.instagram.scrape.schemas import (
    MAX_INSTAGRAM_ITEMS,
    MAX_INSTAGRAM_SOURCES,
)
from app.proprietary.platforms.instagram import (
    InstagramHashtag,
    InstagramPlace,
    InstagramProfile,
)

InstagramDetailItem = Annotated[
    InstagramProfile | InstagramHashtag | InstagramPlace,
    Field(discriminator="detailKind"),
]


class DetailsInput(BaseModel):
    urls: list[str] = Field(
        default_factory=list,
        max_length=MAX_INSTAGRAM_SOURCES,
        description=(
            "Profile / hashtag / place URLs (or bare profile IDs). The URL type "
            "determines the detail kind. Provide these OR search_queries."
        ),
    )
    search_queries: list[str] = Field(
        default_factory=list,
        max_length=MAX_INSTAGRAM_SOURCES,
        description="Discovery keywords. Provide these OR urls (never both).",
    )
    search_type: Literal["hashtag", "profile", "place"] = Field(
        default="hashtag",
        description="What to discover from search_queries (no 'user' — use instagram.scrape).",
    )
    search_limit: int = Field(
        default=10,
        ge=1,
        le=MAX_INSTAGRAM_ITEMS,
        description="Max discovered entities per query.",
    )
    max_items: int = Field(
        default=10,
        ge=1,
        le=MAX_INSTAGRAM_ITEMS,
        description="Max total detail items to return.",
    )

    @model_validator(mode="after")
    def _exactly_one_source(self) -> DetailsInput:
        if not self.urls and not self.search_queries:
            raise ValueError(
                "Provide at least one of 'urls' or 'search_queries'."
            )
        if self.urls and self.search_queries:
            raise ValueError(
                "Provide 'urls' OR 'search_queries', not both (they cannot be combined)."
            )
        return self

    @property
    def estimated_units(self) -> int:
        return self.max_items


class DetailsOutput(BaseModel):
    items: list[InstagramDetailItem] = Field(
        default_factory=list,
        description="One item per profile/hashtag/place, keyed by detailKind.",
    )

    @property
    def billable_units(self) -> int:
        return len(self.items)
