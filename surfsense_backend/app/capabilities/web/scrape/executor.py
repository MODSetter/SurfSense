"""``web.scrape`` executor: fetch each URL in the array → cleaned rows."""

from __future__ import annotations

from app.capabilities.core import Executor
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
        outcomes = [await engine.crawl_url(url) for url in payload.urls]
        rows = [
            _to_row(url, outcome, payload.max_length)
            for url, outcome in zip(payload.urls, outcomes, strict=True)
        ]
        return ScrapeOutput(
            rows=rows,
            captcha_attempts=sum(o.captcha_attempts for o in outcomes),
            captcha_solved=sum(1 for o in outcomes if o.captcha_solved),
        )

    return execute


def _to_row(url: str, outcome: CrawlOutcome, max_length: int) -> ScrapeRow:
    if outcome.status is CrawlOutcomeStatus.SUCCESS and outcome.result:
        content = outcome.result.get("content")
        if content is not None:
            content = content[:max_length]
        return ScrapeRow(
            url=url,
            status="success",
            content=content,
            metadata=outcome.result.get("metadata"),
        )
    status = "empty" if outcome.status is CrawlOutcomeStatus.EMPTY else "failed"
    return ScrapeRow(url=url, status=status, error=outcome.error)
