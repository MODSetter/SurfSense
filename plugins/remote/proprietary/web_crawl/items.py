"""A crawled page as the tool returns it, in the backend capability's wire shape."""

from typing import Any

from proprietary.web_crawl.connector import CrawlOutcomeStatus
from proprietary.web_crawl.site_crawler import CrawlPage

_STATUS_LABEL: dict[CrawlOutcomeStatus, str] = {
    CrawlOutcomeStatus.SUCCESS: "success",
    CrawlOutcomeStatus.EMPTY: "empty",
    CrawlOutcomeStatus.FAILED: "failed",
}


def crawl_item(page: CrawlPage, max_length: int) -> dict[str, Any]:
    """``markdown`` is cut at ``max_length`` characters."""
    return {
        "url": page.url,
        "status": _STATUS_LABEL[page.status],
        "crawl": {
            "loadedUrl": page.loaded_url or page.url,
            "depth": page.depth,
            "referrerUrl": page.referrer,
        },
        "markdown": page.content[:max_length] if page.content is not None else None,
        "metadata": page.metadata,
        "contacts": page.contacts,
        "links": list(page.links or []),
        "error": page.error,
    }
