"""``google_search.scrape`` executor: verb input → scraper → SERP items."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.capabilities.core import Executor
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
        items = await scrape_fn(actor_input, limit=_MAX_SERP_ITEMS)
        return ScrapeOutput(items=items)

    return execute
