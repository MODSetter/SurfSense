"""``instagram.details`` I/O contracts.

A lean surface over ``InstagramScrapeInput`` (``resultsType="details"``). Each
output item is a profile (``detailKind="profile"``, a SurfSense addition; every
other field mirrors the actor). Hashtag/place details are login-walled and
therefore unsupported.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.capabilities.instagram.scrape.schemas import (
    MAX_INSTAGRAM_ITEMS,
    MAX_INSTAGRAM_SOURCES,
)
from app.proprietary.platforms.instagram import InstagramProfile

InstagramDetailItem = InstagramProfile


class DetailsInput(BaseModel):
    urls: list[str] = Field(
        default_factory=list,
        max_length=MAX_INSTAGRAM_SOURCES,
        description=(
            "Profile URLs or bare profile IDs. Provide these OR search_queries."
        ),
    )
    search_queries: list[str] = Field(
        default_factory=list,
        max_length=MAX_INSTAGRAM_SOURCES,
        description="Discovery keywords resolved to profiles. Provide these OR urls.",
    )
    search_type: Literal["profile", "user"] = Field(
        default="profile",
        description="Discovery kind (profile-only; hashtag/place are login-walled).",
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
            raise ValueError("Provide at least one of 'urls' or 'search_queries'.")
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
        description="One profile detail item per resolved profile.",
    )

    @property
    def billable_units(self) -> int:
        return len(self.items)
