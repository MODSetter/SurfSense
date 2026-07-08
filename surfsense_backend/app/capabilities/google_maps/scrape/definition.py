"""``google_maps.scrape`` capability registration (dual-metered: billed per
place via ``GOOGLE_MAPS_MICROS_PER_PLACE`` plus per attached review via
``GOOGLE_MAPS_MICROS_PER_REVIEW``)."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability
from app.capabilities.google_maps.scrape.executor import build_scrape_executor
from app.capabilities.google_maps.scrape.schemas import ScrapeInput, ScrapeOutput

GOOGLE_MAPS_SCRAPE = Capability(
    name="google_maps.scrape",
    description=(
        "Scrape public Google Maps places, details, reviews, and photos. Use "
        "search_queries, urls, or place IDs."
    ),
    input_schema=ScrapeInput,
    output_schema=ScrapeOutput,
    executor=build_scrape_executor(),
    billing_unit=BillingUnit.GOOGLE_MAPS_PLACE,
    docs_url="/docs/connectors/native/google-maps",
)

register_capability(GOOGLE_MAPS_SCRAPE)
