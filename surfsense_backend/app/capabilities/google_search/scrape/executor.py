"""``google_search.scrape`` executor: verb input → scraper → SERP items."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.capabilities.core import Executor
from app.capabilities.core.progress import emit_progress
from app.capabilities.google_search.scrape.schemas import (
    MAX_PAGES_PER_QUERY,
    MAX_SEARCH_QUERIES,
    ScrapeInput,
    ScrapeOutput,
)
from app.proprietary.platforms.google_search import (
    GoogleSearchScrapeInput,
    scrape_serps,
)

ScrapeFn = Callable[..., Awaitable[list[dict]]]

# Hard ceiling on SERP pages returned per call (protects the run regardless of
# how queries * max_pages_per_query multiply out).
_MAX_SERP_ITEMS = MAX_SEARCH_QUERIES * MAX_PAGES_PER_QUERY


def build_scrape_executor(scrape_fn: ScrapeFn | None = None) -> Executor:
    """Bind the executor to a scraper fn (defaults to the proprietary actor)."""
    scrape_fn = scrape_fn or scrape_serps

    async def execute(payload: ScrapeInput) -> ScrapeOutput:
        actor_input = GoogleSearchScrapeInput(
            queries="\n".join(payload.queries),
            maxPagesPerQuery=payload.max_pages_per_query,
            countryCode=payload.country_code,
            languageCode=payload.language_code,
            site=payload.site,
        )
        emit_progress(
            "starting",
            f"Searching {len(payload.queries)} query(ies)",
            total=_MAX_SERP_ITEMS,
            unit="page",
        )
        items = await scrape_fn(actor_input, limit=_MAX_SERP_ITEMS)
        emit_progress(
            "done",
            f"Scraped {len(items)} SERP page(s)",
            current=len(items),
            unit="page",
        )
        return ScrapeOutput(items=items)

    return execute
