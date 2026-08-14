"""``instagram.scrape`` capability registration (billed per item; see config
``INSTAGRAM_SCRAPE_MICROS_PER_ITEM``)."""

from __future__ import annotations

from app.capabilities.core import (
    ActivityDescriptor,
    BillingUnit,
    Capability,
    register_capability,
)
from app.capabilities.instagram.scrape.executor import build_scrape_executor
from app.capabilities.instagram.scrape.schemas import ScrapeInput, ScrapeOutput

INSTAGRAM_SCRAPE = Capability(
    name="instagram.scrape",
    description=(
        "Scrape public Instagram posts or reels from profile/post/reel URLs, "
        "or discover public profiles via search queries."
    ),
    input_schema=ScrapeInput,
    output_schema=ScrapeOutput,
    executor=build_scrape_executor(),
    billing_unit=BillingUnit.INSTAGRAM_ITEM,
    docs_url="/docs/connectors/native/instagram",
    activity=ActivityDescriptor(
        active_title="Searching Instagram",
        completed_title="Searched Instagram",
        category="research",
        icon_key="search",
        integration_key="instagram",
    ),
)

register_capability(INSTAGRAM_SCRAPE)
