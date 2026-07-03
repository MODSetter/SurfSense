"""``web.crawl`` executor: seeds → site spider → one cleaned item per fetched page.

Boundary owned elsewhere: the crawl frontier/fetch live in the proprietary engine
(``app.proprietary.web_crawler``). This executor only maps the engine's
``CrawlPage`` list onto the typed ``CrawlOutput`` (status labels, truncation, and
the captcha telemetry the billing seam reads).
"""

from __future__ import annotations

from app.capabilities.core import Executor
from app.capabilities.web.crawl.schemas import (
    CrawlInput,
    CrawlItem,
    CrawlMeta,
    CrawlOutput,
)
from app.proprietary.web_crawler import (
    CrawlOutcomeStatus,
    CrawlPage,
    WebCrawlerConnector,
    crawl_site,
)

_STATUS_LABEL: dict[CrawlOutcomeStatus, str] = {
    CrawlOutcomeStatus.SUCCESS: "success",
    CrawlOutcomeStatus.EMPTY: "empty",
    CrawlOutcomeStatus.FAILED: "failed",
}


def build_crawl_executor(engine: WebCrawlerConnector | None = None) -> Executor:
    """Build the ``web.crawl`` executor, optionally over an injected engine (tests)."""
    crawler = engine or WebCrawlerConnector()

    async def execute(payload: CrawlInput) -> CrawlOutput:
        pages = await crawl_site(
            crawler,
            payload.startUrls,
            max_crawl_depth=payload.maxCrawlDepth,
            max_crawl_pages=payload.maxCrawlPages,
        )
        return CrawlOutput(
            items=[_to_item(page, payload.maxLength) for page in pages],
            captcha_attempts=sum(page.captcha_attempts for page in pages),
            captcha_solved=sum(1 for page in pages if page.captcha_solved),
        )

    return execute


def _to_item(page: CrawlPage, max_length: int) -> CrawlItem:
    content = page.content[:max_length] if page.content is not None else None
    return CrawlItem(
        url=page.url,
        status=_STATUS_LABEL[page.status],
        crawl=CrawlMeta(
            loadedUrl=page.loaded_url or page.url,
            depth=page.depth,
            referrerUrl=page.referrer,
        ),
        markdown=content,
        metadata=page.metadata,
        error=page.error,
    )
