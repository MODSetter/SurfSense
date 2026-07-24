"""Proprietary web crawler engine (non-Apache-2; see ``app/proprietary/LICENSE``).

Public API for the single-framework (Scrapling) undetectable crawler. Callers
depend only on these symbols, never on internal tier/strategy details.
"""

from app.proprietary.web_crawler.connector import (
    CrawlOutcome,
    CrawlOutcomeStatus,
    WebCrawlerConnector,
)
from app.proprietary.web_crawler.site_crawler import CrawlPage, crawl_site

__all__ = [
    "CrawlOutcome",
    "CrawlOutcomeStatus",
    "CrawlPage",
    "WebCrawlerConnector",
    "crawl_site",
]
