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
        "at maxCrawlPages. On a deeper crawl, narrow which links are followed with "
        "includeUrlPatterns / excludeUrlPatterns (regexes). Returns one item per "
        "fetched page with clean markdown content, metadata (title, description), "
        "crawl provenance, every link with its anchor text and kind "
        "(internal/external/social/email/tel — use the text/context to tie a "
        "profile URL to a person or company), and contact signals (emails, phone "
        "numbers, social profiles). The site-wide contacts summary deduplicates "
        "them with provenance: siteWide=true marks footer/header values (the "
        "company's own contacts) vs page-local finds (e.g. team members' "
        "profiles). Useful for lead generation and competitive intelligence; "
        "contact details often live on about/contact/privacy pages, so crawl "
        "with maxCrawlDepth >= 1 to surface them. JS-rendered pages are loaded "
        "in a real browser and auto-scrolled, so lazy-loaded listings "
        "(directories, infinite-scroll feeds) are captured too."
    ),
    input_schema=CrawlInput,
    output_schema=CrawlOutput,
    executor=build_crawl_executor(),
    billing_unit=BillingUnit.WEB_CRAWL,
)

register_capability(WEB_CRAWL)
