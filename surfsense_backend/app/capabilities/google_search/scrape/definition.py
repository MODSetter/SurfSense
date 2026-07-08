"""``google_search.scrape`` capability registration (billed per SERP page; see
config ``GOOGLE_SEARCH_MICROS_PER_SERP``)."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability
from app.capabilities.google_search.scrape.executor import build_scrape_executor
from app.capabilities.google_search.scrape.schemas import ScrapeInput, ScrapeOutput

GOOGLE_SEARCH_SCRAPE = Capability(
    name="google_search.scrape",
    description=(
        "Search Google and return structured SERP results. Use search_queries "
        "or Google Search URLs."
    ),
    input_schema=ScrapeInput,
    output_schema=ScrapeOutput,
    executor=build_scrape_executor(),
    billing_unit=BillingUnit.GOOGLE_SEARCH_SERP,
    docs_url="/docs/connectors/native/google-search",
)

register_capability(GOOGLE_SEARCH_SCRAPE)
