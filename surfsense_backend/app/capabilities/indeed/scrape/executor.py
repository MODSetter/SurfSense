"""``indeed.scrape`` executor: verb input → scraper → Indeed job items."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.capabilities.core import Executor
from app.capabilities.core.progress import emit_progress
from app.capabilities.indeed.scrape.schemas import ScrapeInput, ScrapeOutput
from app.exceptions import ForbiddenError
from app.proprietary.platforms.indeed_jobs import (
    IndeedAccessBlockedError,
    IndeedScrapeInput,
    scrape_indeed,
)

ScrapeFn = Callable[..., Awaitable[list[dict]]]


def build_scrape_executor(scrape_fn: ScrapeFn | None = None) -> Executor:
    """Bind the executor to a scraper fn (defaults to the proprietary actor)."""
    scrape_fn = scrape_fn or scrape_indeed

    async def execute(payload: ScrapeInput) -> ScrapeOutput:
        actor_input = IndeedScrapeInput(
            startUrls=[{"url": url} for url in payload.urls],
            queries=payload.search_queries,
            country=payload.country,
            location=payload.location,
            radius=payload.radius,
            jobType=payload.job_type,
            level=payload.level,
            remote=payload.remote,
            fromDays=payload.from_days,
            sort=payload.sort,
            scrapeJobDetails=payload.scrape_job_details,
            maxItems=payload.max_items,
            maxItemsPerQuery=payload.max_items_per_query,
        )
        emit_progress(
            "starting", "Resolving Indeed targets", total=payload.max_items, unit="job"
        )
        try:
            items = await scrape_fn(actor_input, limit=payload.max_items)
        except IndeedAccessBlockedError as exc:
            # Anonymous-only scraper; a hard block can't be retried with creds.
            raise ForbiddenError(
                f"Indeed refused anonymous access: {exc}",
                code="INDEED_ACCESS_BLOCKED",
            ) from exc
        emit_progress(
            "done", f"Scraped {len(items)} job(s)", current=len(items), unit="job"
        )
        return ScrapeOutput(items=items)

    return execute
