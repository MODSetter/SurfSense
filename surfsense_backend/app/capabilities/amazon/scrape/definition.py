"""Registration for the ``amazon.scrape`` capability."""

from __future__ import annotations

from app.capabilities.amazon.scrape.executor import build_scrape_executor
from app.capabilities.amazon.scrape.schemas import ScrapeInput, ScrapeOutput
from app.capabilities.core import BillingUnit, Capability, register_capability

AMAZON_SCRAPE = Capability(
    name="amazon.scrape",
    description=(
        "Scrape public Amazon product details, search results, offers, sellers, "
        "best-seller rankings, and on-page reviews."
    ),
    input_schema=ScrapeInput,
    output_schema=ScrapeOutput,
    executor=build_scrape_executor(),
    billing_unit=BillingUnit.AMAZON_PRODUCT,
    docs_url="/docs/connectors/native/amazon",
)

register_capability(AMAZON_SCRAPE)
