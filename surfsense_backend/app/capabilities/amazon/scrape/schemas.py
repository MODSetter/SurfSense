"""Input and output contracts for ``amazon.scrape``."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from app.capabilities.core.validation import HttpUrlStr
from app.proprietary.platforms.amazon import ProductItem

MAX_AMAZON_SOURCES = 20
MAX_AMAZON_RESULTS = 1000


class ScrapeInput(BaseModel):
    """Agent-facing controls for public product discovery and enrichment."""

    urls: list[HttpUrlStr] = Field(default_factory=list, max_length=MAX_AMAZON_SOURCES)
    search_terms: list[str] = Field(default_factory=list, max_length=MAX_AMAZON_SOURCES)
    max_items: int = Field(default=10, ge=1, le=100)
    domain: str = Field(
        default="www.amazon.com", pattern=r"^(?:www\.)?amazon\.[a-z.]+$"
    )
    language: str | None = None
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    zip_code: str | None = Field(default=None, min_length=1, max_length=20)
    include_details: bool = True
    max_offers: int = Field(default=0, ge=0, le=100)
    include_sellers: bool = False
    max_variants: int = Field(default=0, ge=0, le=100)
    include_variant_prices: bool = False

    @model_validator(mode="after")
    def _require_source(self) -> ScrapeInput:
        if not (self.urls or self.search_terms):
            raise ValueError("Provide at least one URL or search term.")
        if len(self.urls) + len(self.search_terms) > MAX_AMAZON_SOURCES:
            raise ValueError(
                f"Provide no more than {MAX_AMAZON_SOURCES} combined sources."
            )
        return self

    @property
    def estimated_units(self) -> int:
        """Worst-case returned products within the hard per-run ceiling."""
        search_products = len(self.search_terms) * self.max_items
        direct_products = len(self.urls) * (1 + self.max_variants)
        return min(search_products + direct_products, MAX_AMAZON_RESULTS)


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
