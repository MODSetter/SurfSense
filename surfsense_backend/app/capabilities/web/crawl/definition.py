"""``web.crawl`` capability registration."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability
from app.capabilities.web.crawl.executor import build_crawl_executor
from app.capabilities.web.crawl.schemas import CrawlInput, CrawlOutput

WEB_CRAWL = Capability(
    name="web.crawl",
    description=(
        "Scrape a single web page or crawl a whole website. Give it one or more "
        "startUrls. Set maxCrawlDepth=0 to fetch just those URLs, or higher to "
        "also follow the links on each page (depth 1 = the start pages plus the "
        "pages they link to, and so on) — staying on the same site and stopping "
        "at maxCrawlPages. Returns one item per fetched page with clean markdown "
        "content, metadata (title, description), and crawl provenance."
    ),
    input_schema=CrawlInput,
    output_schema=CrawlOutput,
    executor=build_crawl_executor(),
    billing_unit=BillingUnit.WEB_CRAWL,
)

register_capability(WEB_CRAWL)
