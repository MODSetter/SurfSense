"""Registration for the ``walmart.scrape`` capability."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability
from app.capabilities.walmart.scrape.executor import build_scrape_executor
from app.capabilities.walmart.scrape.schemas import ScrapeInput, ScrapeOutput

WALMART_SCRAPE = Capability(
    name="walmart.scrape",
    description=(
        "Scrape public Walmart product details, search/category listings, "
        "prices, sellers, variants, availability, and a sample of on-page reviews."
    ),
    input_schema=ScrapeInput,
    output_schema=ScrapeOutput,
    executor=build_scrape_executor(),
    billing_unit=BillingUnit.WALMART_PRODUCT,
    docs_url="/docs/connectors/native/walmart",
)

register_capability(WALMART_SCRAPE)
