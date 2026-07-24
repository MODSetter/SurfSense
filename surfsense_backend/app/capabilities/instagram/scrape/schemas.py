"""``instagram.scrape`` I/O contracts.

A lean, agent-friendly surface over ``InstagramScrapeInput``
(``app/proprietary/platforms/instagram``). The executor maps this to the full
scraper input; the scraper's ``InstagramMediaItem`` is reused verbatim as the
output element.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.proprietary.platforms.instagram import InstagramMediaItem

MAX_INSTAGRAM_SOURCES = 20
"""Per-call cap on urls + search_queries: bounds a synchronous request's fan-out."""

MAX_INSTAGRAM_ITEMS = 100
"""Hard ceiling on items returned per call, regardless of the per-target caps."""


class ScrapeInput(BaseModel):
    urls: list[str] = Field(
        default_factory=list,
        max_length=MAX_INSTAGRAM_SOURCES,
        description=(
            "Instagram URLs or bare profile IDs: profile, post (/p/), or reel "
            "(/reel/). Hashtag/place URLs are unsupported (login-walled). "
            "Provide these OR search_queries (never both)."
        ),
    )
    search_queries: list[str] = Field(
        default_factory=list,
        max_length=MAX_INSTAGRAM_SOURCES,
        description=(
            "Discovery keywords resolved to profiles via Google (IG's keyword "
            "search is login-walled). Provide these OR urls (never both)."
        ),
    )
    search_type: Literal["profile", "user"] = Field(
        default="profile",
        description="Discovery kind (profile-only; hashtag/place are login-walled).",
    )
    result_type: Literal["posts", "reels"] = Field(
        default="posts",
        description="Which feed to return: 'posts' or 'reels'.",
    )
    newer_than: str | None = Field(
        default=None,
        description=(
            "Only return posts newer than this: YYYY-MM-DD, ISO timestamp, or "
            "relative ('1 day', '2 months'); UTC."
        ),
    )
    skip_pinned_posts: bool = Field(
        default=False,
        description="Exclude pinned posts (posts mode).",
    )
    max_per_target: int = Field(
        default=10,
        ge=1,
        description="Max results per URL or per discovered target.",
    )
    max_items: int = Field(
        default=10,
        ge=1,
        le=MAX_INSTAGRAM_ITEMS,
        description="Max total items to return across all sources.",
    )
    add_parent_data: bool = Field(
        default=False,
        description="Attach a dataSource block to each feed item.",
    )

    @model_validator(mode="after")
    def _exactly_one_source(self) -> ScrapeInput:
        if not self.urls and not self.search_queries:
            raise ValueError("Provide at least one of 'urls' or 'search_queries'.")
        if self.urls and self.search_queries:
            raise ValueError(
                "Provide 'urls' OR 'search_queries', not both (they cannot be combined)."
            )
        return self

    @property
    def estimated_units(self) -> int:
        """Worst-case billable items for the pre-flight gate: ``max_items`` is a
        hard cross-source ceiling (le=100), so no call can exceed it."""
        return self.max_items


class ScrapeOutput(BaseModel):
    items: list[InstagramMediaItem] = Field(
        default_factory=list,
        description="One media item per result (post/reel/mention), in emission order.",
    )

    @property
    def billable_units(self) -> int:
        """One returned item = one billable unit."""
        return len(self.items)
