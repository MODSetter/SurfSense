"""``youtube.scrape`` I/O contracts.

A lean, agent-friendly surface over the Apify-compatible ``YouTubeScrapeInput``
(``app/proprietary/platforms/youtube``). The executor maps this to the full actor
input; the actor's ``VideoItem`` is reused verbatim as the output element so the
verb stays parity-faithful with the underlying Apify shape.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from app.proprietary.platforms.youtube import VideoItem

MAX_YOUTUBE_SOURCES = 20
"""Per-call cap on URLs + queries: bounds a synchronous request's fan-out (05)."""


class ScrapeInput(BaseModel):
    urls: list[str] = Field(
        default_factory=list,
        max_length=MAX_YOUTUBE_SOURCES,
        description=(
            "YouTube URLs to scrape: video, channel (/@handle or /channel/UC...), "
            "playlist (?list=...), shorts, or hashtag pages. Provide these OR "
            "search_queries (at least one is required)."
        ),
    )
    search_queries: list[str] = Field(
        default_factory=list,
        max_length=MAX_YOUTUBE_SOURCES,
        description=(
            "Search terms to run on YouTube; each returns up to max_results videos. "
            "Provide these OR urls (at least one is required)."
        ),
    )
    max_results: int = Field(
        default=10,
        ge=1,
        le=1000,
        description=(
            "Max items to return per source and per content type (videos, shorts, "
            "streams are capped independently for a channel)."
        ),
    )
    download_subtitles: bool = Field(
        default=False,
        description="Also fetch each video's subtitle track (slower; more requests).",
    )
    subtitles_language: str = Field(
        default="en",
        description="Subtitle language code (e.g. 'en', 'fr'). Used when download_subtitles is true.",
    )

    @model_validator(mode="after")
    def _require_a_source(self) -> ScrapeInput:
        if not self.urls and not self.search_queries:
            raise ValueError("Provide at least one of 'urls' or 'search_queries'.")
        return self


class ScrapeOutput(BaseModel):
    items: list[VideoItem] = Field(
        default_factory=list,
        description="One video item per result, in the scraper's emission order.",
    )
