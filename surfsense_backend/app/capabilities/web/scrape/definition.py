"""``web.scrape`` capability registration."""

from __future__ import annotations

from app.capabilities.store import register_capability
from app.capabilities.types import BillingUnit, Capability
from app.capabilities.web.scrape.executor import build_scrape_executor
from app.capabilities.web.scrape.schemas import ScrapeInput, ScrapeOutput

WEB_SCRAPE = Capability(
    name="web.scrape",
    input_schema=ScrapeInput,
    output_schema=ScrapeOutput,
    executor=build_scrape_executor(),
    billing_unit=BillingUnit.WEB_CRAWL,
)

register_capability(WEB_SCRAPE)
