"""``tiktok.scrape`` capability registration (billed per video; see config
``TIKTOK_MICROS_PER_VIDEO``)."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability
from app.capabilities.tiktok.scrape.executor import build_scrape_executor
from app.capabilities.tiktok.scrape.schemas import ScrapeInput, ScrapeOutput

TIKTOK_SCRAPE = Capability(
    name="tiktok.scrape",
    description=(
        "Scrape public TikTok videos. Use urls, profiles, hashtags, or "
        "search_queries."
    ),
    input_schema=ScrapeInput,
    output_schema=ScrapeOutput,
    executor=build_scrape_executor(),
    billing_unit=BillingUnit.TIKTOK_VIDEO,
    docs_url="/docs/connectors/native/tiktok",
)

register_capability(TIKTOK_SCRAPE)
