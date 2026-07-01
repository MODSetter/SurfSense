"""``web.scrape`` executor: fetch each URL in the array → cleaned rows."""

from __future__ import annotations

from app.capabilities.types import Executor
from app.capabilities.web.scrape.schemas import ScrapeInput, ScrapeOutput, ScrapeRow
from app.proprietary.web_crawler import (
    CrawlOutcome,
    CrawlOutcomeStatus,
    WebCrawlerConnector,
)


def build_scrape_executor(engine: WebCrawlerConnector | None = None) -> Executor:
    """Bind the executor to a fetch engine (defaults to the proprietary crawler)."""
    engine = engine or WebCrawlerConnector()

    async def execute(payload: ScrapeInput) -> ScrapeOutput:
        rows = [_to_row(url, await engine.crawl_url(url)) for url in payload.urls]
        return ScrapeOutput(rows=rows)

    return execute


def _to_row(url: str, outcome: CrawlOutcome) -> ScrapeRow:
    if outcome.status is CrawlOutcomeStatus.SUCCESS and outcome.result:
        return ScrapeRow(
            url=url,
            status="success",
            content=outcome.result.get("content"),
            metadata=outcome.result.get("metadata"),
        )
    status = "empty" if outcome.status is CrawlOutcomeStatus.EMPTY else "failed"
    return ScrapeRow(url=url, status=status, error=outcome.error)
