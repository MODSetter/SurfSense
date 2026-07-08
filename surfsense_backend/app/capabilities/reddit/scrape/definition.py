"""``reddit.scrape`` capability registration (billed per item; see config
``REDDIT_SCRAPE_MICROS_PER_ITEM``)."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability
from app.capabilities.reddit.scrape.executor import build_scrape_executor
from app.capabilities.reddit.scrape.schemas import ScrapeInput, ScrapeOutput

REDDIT_SCRAPE = Capability(
    name="reddit.scrape",
    description=(
        "Scrape public Reddit posts, comments, and metadata. Use urls or "
        "search_queries."
    ),
    input_schema=ScrapeInput,
    output_schema=ScrapeOutput,
    executor=build_scrape_executor(),
    billing_unit=BillingUnit.REDDIT_ITEM,
    docs_url="/docs/connectors/native/reddit",
)

register_capability(REDDIT_SCRAPE)
