# ruff: noqa: N815 - field names mirror the public camelCase TikTok/Apify API
"""Input surface for the TikTok scraper, shaped to the Clockworks actor.

Anonymous only: no auth-shaped field exists here. Fields the Phase-1 blob-first
path does not yet act on (media downloads, follower add-ons) are still accepted
via ``extra="allow"`` for contract parity and land inert.

Caps (``resultsPerPage``) are per-target counts; the cross-target ceiling is
caller policy applied by the collector, never baked into the flows.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ProfileSorting = Literal["latest", "popular", "oldest"]
ProfileSection = Literal["videos", "reposts"]
SearchSection = Literal["", "/video", "/user"]


class StartUrl(BaseModel):
    """A single direct URL entry (``{"url": ...}``; extra keys ignored)."""

    model_config = ConfigDict(extra="allow")

    url: str


class TikTokScrapeInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    # Discovery
    startUrls: list[StartUrl] = Field(default_factory=list)
    hashtags: list[str] = Field(default_factory=list)
    profiles: list[str] = Field(default_factory=list)
    searchQueries: list[str] = Field(default_factory=list)
    postURLs: list[str] = Field(default_factory=list)

    # Per-target count
    resultsPerPage: int = Field(default=1, ge=1)

    # Profile options
    profileScrapeSections: list[ProfileSection] = Field(
        default_factory=lambda: ["videos"]
    )
    profileSorting: ProfileSorting = "latest"
    excludePinnedPosts: bool = False

    # Search options
    searchSection: SearchSection = ""
    maxProfilesPerQuery: int = Field(default=10, ge=1)

    # Incremental filters (ISO date or relative "<n> days" per the actor)
    oldestPostDateUnified: str | None = None
    newestPostDate: str | None = None

    # Proxy
    proxyCountryCode: str = "None"
