"""``web.crawl`` capability registration."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability
from app.capabilities.web.crawl.executor import build_crawl_executor
from app.capabilities.web.crawl.schemas import CrawlInput, CrawlOutput

WEB_CRAWL = Capability(
    name="web.crawl",
    description=(
        "Scrape pages or crawl websites for clean markdown, links, metadata, "
        "and contact signals. Use startUrls and crawl-depth controls."
    ),
    input_schema=CrawlInput,
    output_schema=CrawlOutput,
    executor=build_crawl_executor(),
    billing_unit=BillingUnit.WEB_CRAWL,
    docs_url="/docs/connectors/native/web-crawl",
)

register_capability(WEB_CRAWL)
