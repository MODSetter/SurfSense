"""``indeed.scrape`` I/O contracts.

A lean, agent-friendly surface over ``IndeedScrapeInput``
(``app/proprietary/platforms/indeed_jobs``). The executor maps this to the full
scraper input; the scraper's ``IndeedItem`` is reused verbatim as the output
element.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from app.proprietary.platforms.indeed_jobs import IndeedItem
from app.proprietary.platforms.indeed_jobs.schemas import (
    IndeedJobType,
    IndeedLevel,
    IndeedRemote,
    IndeedSort,
)

MAX_INDEED_SOURCES = 20
"""Per-call cap on urls + search_queries: bounds a synchronous request's fan-out."""

MAX_INDEED_ITEMS = 100
"""Hard ceiling on jobs returned per call, regardless of the per-query caps."""


class ScrapeInput(BaseModel):
    urls: list[str] = Field(
        default_factory=list,
        max_length=MAX_INDEED_SOURCES,
        description=(
            "Indeed URLs to scrape: a search page (/jobs?q=&l=) or a company "
            "jobs page (/cmp/<slug>/jobs). Provide these OR search_queries "
            "(at least one source is required)."
        ),
    )
    search_queries: list[str] = Field(
        default_factory=list,
        max_length=MAX_INDEED_SOURCES,
        description=(
            "Job search terms; each returns up to max_items_per_query results, "
            "shaped by country/location/job_type/etc."
        ),
    )
    country: str = Field(
        default="us",
        description="Country code selecting the Indeed domain, e.g. 'us', 'gb', 'de'.",
    )
    location: str | None = Field(
        default=None,
        description="Where to search, e.g. 'Remote', 'New York, NY'.",
    )
    radius: int | None = Field(
        default=None,
        description="Search radius in miles/km around location.",
    )
    job_type: IndeedJobType | None = Field(
        default=None,
        description="Employment type filter: fulltime, parttime, contract, etc.",
    )
    level: IndeedLevel | None = Field(
        default=None,
        description="Experience level filter: entry_level, mid_level, senior_level.",
    )
    remote: IndeedRemote | None = Field(
        default=None,
        description="Work model filter: remote or hybrid.",
    )
    from_days: int | None = Field(
        default=None,
        description="Only return jobs posted within the last N days.",
    )
    sort: IndeedSort = Field(
        default="relevance",
        description="Result ordering: relevance or date.",
    )
    max_items: int = Field(
        default=25,
        ge=1,
        le=MAX_INDEED_ITEMS,
        description="Max total jobs to return across all sources.",
    )
    max_items_per_query: int = Field(
        default=25,
        ge=0,
        description="Max jobs to pull per search/company target.",
    )

    @model_validator(mode="after")
    def _require_a_source(self) -> ScrapeInput:
        if not self.urls and not self.search_queries:
            raise ValueError("Provide at least one of 'urls' or 'search_queries'.")
        return self

    @property
    def estimated_units(self) -> int:
        """Worst-case billable jobs for the pre-flight gate: ``max_items`` is a
        hard cross-source ceiling (le=100), so no call can exceed it."""
        return self.max_items


class ScrapeOutput(BaseModel):
    items: list[IndeedItem] = Field(
        default_factory=list,
        description="One item per job posting, in emission order.",
    )

    @property
    def billable_units(self) -> int:
        """One returned job = one billable unit."""
        return len(self.items)
