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
        "Scrape public Google Maps places. Give it search queries (optionally "
        "scoped by location), Google Maps URLs, or place IDs, and it returns "
        "structured place items — name, address, category, phone, website, "
        "rating, review count, coordinates, and opening hours. Set "
        "include_details for richer detail-page fields, or max_reviews/"
        "max_images to attach reviews and photos per place."
    ),
    input_schema=ScrapeInput,
    output_schema=ScrapeOutput,
    executor=build_scrape_executor(),
    billing_unit=BillingUnit.GOOGLE_MAPS_PLACE,
)

register_capability(GOOGLE_MAPS_SCRAPE)
