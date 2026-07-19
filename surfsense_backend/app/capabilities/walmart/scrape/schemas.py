"""Input and output contracts for ``walmart.scrape``."""

from __future__ import annotations

from urllib.parse import quote_plus

from pydantic import BaseModel, Field, model_validator

from app.proprietary.platforms.walmart import ProductItem

MAX_WALMART_SOURCES = 20
MAX_WALMART_RESULTS = 1000


class ScrapeInput(BaseModel):
    """Agent-facing controls for public Walmart product discovery and enrichment."""

    urls: list[str] = Field(default_factory=list, max_length=MAX_WALMART_SOURCES)
    search_terms: list[str] = Field(
        default_factory=list, max_length=MAX_WALMART_SOURCES
    )
    max_items: int = Field(default=10, ge=1, le=100)
    include_details: bool = True
    include_reviews_sample: bool = True

    @model_validator(mode="after")
    def _require_source(self) -> ScrapeInput:
        if not (self.urls or self.search_terms):
            raise ValueError("Provide at least one URL or search term.")
        if len(self.urls) + len(self.search_terms) > MAX_WALMART_SOURCES:
            raise ValueError(
                f"Provide no more than {MAX_WALMART_SOURCES} combined sources."
            )
        return self

    def start_urls(self) -> list[str]:
        """Direct URLs plus a search URL synthesized per search term."""
        searches = [
            f"https://www.walmart.com/search?q={quote_plus(term)}"
            for term in self.search_terms
        ]
        return [*self.urls, *searches]

    @property
    def estimated_units(self) -> int:
        """Worst-case returned products within the hard per-run ceiling."""
        search_products = len(self.search_terms) * self.max_items
        direct_products = len(self.urls) * self.max_items
        return min(search_products + direct_products, MAX_WALMART_RESULTS)


class ScrapeOutput(BaseModel):
    """Products and structured per-input errors in emission order."""

    items: list[ProductItem] = Field(default_factory=list)

    @property
    def billable_units(self) -> int:
        """Count successful products; error items are never billed."""
        return sum(
            1
            for item in self.items
            if not (item.model_extra and item.model_extra.get("error"))
        )
