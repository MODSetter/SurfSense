"""``google_search.scrape`` I/O contracts.

A lean, agent-friendly surface over ``GoogleSearchScrapeInput``
(``app/proprietary/platforms/google_search``). The executor maps this to the
full scraper input; the scraper's ``SerpItem`` is reused verbatim as the output
element.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.proprietary.platforms.google_search import SerpItem

MAX_SEARCH_QUERIES = 20
"""Per-call cap on queries: bounds a synchronous request's fan-out."""

MAX_PAGES_PER_QUERY = 10
"""Deepest result-page pagination a single query will follow."""


class ScrapeInput(BaseModel):
    queries: list[str] = Field(
        min_length=1,
        max_length=MAX_SEARCH_QUERIES,
        description=(
            "Search terms (e.g. 'wedding photographers denver') or full Google "
            "Search URLs. Each term is searched; each URL is scraped as-is."
        ),
    )
    max_pages_per_query: int = Field(
        default=1,
        ge=1,
        le=MAX_PAGES_PER_QUERY,
        description="Result pages to fetch per query (1 = first page only).",
    )
    country_code: str | None = Field(
        default=None,
        description="Two-letter country to search from, e.g. 'us', 'fr'.",
    )
    language_code: str = Field(
        default="",
        description="Result language code, e.g. 'en', 'fr' (blank = Google default).",
    )
    site: str | None = Field(
        default=None,
        description="Restrict results to a single domain, e.g. 'example.com'.",
    )


class ScrapeOutput(BaseModel):
    items: list[SerpItem] = Field(
        default_factory=list,
        description="One item per fetched SERP page, in the scraper's emission order.",
    )
