"""``tiktok.scrape`` I/O contracts.

A lean, agent-friendly surface over ``TikTokScrapeInput``
(``app/proprietary/platforms/tiktok``). The executor maps this to the full
scraper input; the scraper's ``TikTokVideoItem`` is reused verbatim as the
output element. Any TikTok URL kind (video, profile, hashtag, search) goes in
``urls``; ``profiles``/``hashtags`` are typed shortcuts. Keyword search is not a
video source here — use ``tiktok.user_search`` to find accounts by keyword.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from app.proprietary.platforms.tiktok import TikTokVideoItem

MAX_TIKTOK_SOURCES = 20
"""Per-call cap on each source list: bounds a synchronous request's fan-out."""

MAX_TIKTOK_ITEMS = 100
"""Hard ceiling on items returned per call, regardless of the per-target count."""


class ScrapeInput(BaseModel):
    urls: list[str] = Field(
        default_factory=list,
        max_length=MAX_TIKTOK_SOURCES,
        description=(
            "TikTok URLs to scrape: a video, a profile (/@<user>), a hashtag "
            "(/tag/<name>), or a search URL. Provide these OR profiles/hashtags "
            "(at least one source is required)."
        ),
    )
    profiles: list[str] = Field(
        default_factory=list,
        max_length=MAX_TIKTOK_SOURCES,
        description="Profile usernames (with or without a leading '@').",
    )
    hashtags: list[str] = Field(
        default_factory=list,
        max_length=MAX_TIKTOK_SOURCES,
        description="Hashtag names to scrape, without the leading '#'.",
    )
    results_per_page: int = Field(
        default=10,
        ge=1,
        le=MAX_TIKTOK_ITEMS,
        description="Max videos to pull per profile/hashtag target.",
    )
    max_items: int = Field(
        default=10,
        ge=1,
        le=MAX_TIKTOK_ITEMS,
        description="Max total items to return across all sources.",
    )

    @model_validator(mode="after")
    def _require_a_source(self) -> ScrapeInput:
        if not any((self.urls, self.profiles, self.hashtags)):
            raise ValueError(
                "Provide at least one of 'urls', 'profiles', or 'hashtags'."
            )
        return self

    @property
    def estimated_units(self) -> int:
        """Worst-case billable items for the pre-flight gate: ``max_items`` is a
        hard cross-source ceiling (le=100), so no call can exceed it."""
        return self.max_items


class ScrapeOutput(BaseModel):
    items: list[TikTokVideoItem] = Field(
        default_factory=list,
        description="One item per video returned, in emission order.",
    )

    @property
    def billable_units(self) -> int:
        """One returned video = one billable unit; ErrorItems (``errorCode`` set,
        for blocked/empty targets) are surfaced but never charged."""
        return sum(1 for item in self.items if not getattr(item, "errorCode", None))
