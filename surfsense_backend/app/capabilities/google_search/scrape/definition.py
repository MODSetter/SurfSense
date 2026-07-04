"""``google_search.scrape`` capability registration (free — see 04-capabilities open item)."""

from __future__ import annotations

from app.capabilities.core import Capability, register_capability
from app.capabilities.google_search.scrape.executor import build_scrape_executor
from app.capabilities.google_search.scrape.schemas import ScrapeInput, ScrapeOutput

GOOGLE_SEARCH_SCRAPE = Capability(
    name="google_search.scrape",
    description=(
        "Search Google and return structured results. Give it search terms "
        "(optionally scoped by country/language or to a single site) or full "
        "Google Search URLs, and it returns SERP items — organic results "
        "(title, url, description), related queries, people-also-ask, and any "
        "AI overview. Use max_pages_per_query to page deeper."
    ),
    input_schema=ScrapeInput,
    output_schema=ScrapeOutput,
    executor=build_scrape_executor(),
    billing_unit=None,
)

register_capability(GOOGLE_SEARCH_SCRAPE)
