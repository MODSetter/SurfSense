"""SurfSense's web crawler: one page's text, or a site crawled to a depth, as clean markdown."""

from proprietary.web_crawl.connector import (
    CrawlOutcome,
    CrawlOutcomeStatus,
    WebCrawlerConnector,
)
from proprietary.web_crawl.site_crawler import CrawlPage, crawl_site

__all__ = [
    "CrawlOutcome",
    "CrawlOutcomeStatus",
    "CrawlPage",
    "WebCrawlerConnector",
    "crawl_site",
]
