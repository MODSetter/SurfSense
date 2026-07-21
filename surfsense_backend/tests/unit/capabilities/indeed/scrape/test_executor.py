"""``indeed.scrape`` executor: verb input → actor input mapping → typed items.

Boundary mocked: the proprietary scraper (injected fake). NOT mocked: the verb's
own payload→IndeedScrapeInput mapping and the dict→IndeedItem wrapping.
"""

from __future__ import annotations

import pytest

from app.capabilities.indeed.scrape.executor import build_scrape_executor
from app.capabilities.indeed.scrape.schemas import ScrapeInput, ScrapeOutput
from app.exceptions import ForbiddenError
from app.proprietary.platforms.indeed_jobs import (
    IndeedAccessBlockedError,
    IndeedScrapeInput,
)

pytestmark = pytest.mark.unit


class _FakeScraper:
    """Records the actor input + limit it was called with; returns canned items."""

    def __init__(self, items: list[dict]):
        self._items = items
        self.calls: list[tuple[IndeedScrapeInput, int | None]] = []

    async def __call__(
        self, actor_input: IndeedScrapeInput, *, limit: int | None = None
    ) -> list[dict]:
        self.calls.append((actor_input, limit))
        return self._items


async def test_maps_urls_to_start_urls_and_wraps_items():
    scraper = _FakeScraper([{"jobKey": "abc", "title": "Data Analyst"}])
    execute = build_scrape_executor(scrape_fn=scraper)

    out = await execute(ScrapeInput(urls=["https://www.indeed.com/jobs?q=dev"]))

    assert isinstance(out, ScrapeOutput)
    assert len(out.items) == 1
    assert out.items[0].jobKey == "abc"
    assert out.items[0].title == "Data Analyst"

    (actor_input, _limit) = scraper.calls[0]
    assert [u.url for u in actor_input.startUrls] == [
        "https://www.indeed.com/jobs?q=dev"
    ]
    assert actor_input.queries == []


async def test_maps_search_params_and_passes_limit():
    scraper = _FakeScraper([])
    execute = build_scrape_executor(scrape_fn=scraper)

    await execute(
        ScrapeInput(
            search_queries=["data analyst"],
            country="gb",
            location="Remote",
            job_type="fulltime",
            level="entry_level",
            remote="remote",
            from_days=7,
            sort="date",
            max_items=40,
            max_items_per_query=15,
        )
    )

    (actor_input, limit) = scraper.calls[0]
    assert actor_input.queries == ["data analyst"]
    assert actor_input.country == "gb"
    assert actor_input.location == "Remote"
    assert actor_input.jobType == "fulltime"
    assert actor_input.level == "entry_level"
    assert actor_input.remote == "remote"
    assert actor_input.fromDays == 7
    assert actor_input.sort == "date"
    assert actor_input.maxItems == 40
    assert actor_input.maxItemsPerQuery == 15
    # The outer collection limit is the caller's total-item cap.
    assert limit == 40


async def test_access_blocked_maps_to_forbidden():
    async def _blocked(actor_input: IndeedScrapeInput, *, limit: int | None = None):
        raise IndeedAccessBlockedError("all IPs refused")

    execute = build_scrape_executor(scrape_fn=_blocked)

    with pytest.raises(ForbiddenError):
        await execute(ScrapeInput(search_queries=["x"]))


def test_requires_a_source():
    with pytest.raises(ValueError, match="at least one"):
        ScrapeInput()
