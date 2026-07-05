"""``reddit.scrape`` executor: verb input → actor input mapping → typed items.

Boundary mocked: the proprietary scraper (injected fake). NOT mocked: the verb's
own payload→RedditScrapeInput mapping and the dict→RedditItem wrapping.
"""

from __future__ import annotations

import pytest

from app.capabilities.reddit.scrape.executor import build_scrape_executor
from app.capabilities.reddit.scrape.schemas import ScrapeInput, ScrapeOutput
from app.exceptions import ForbiddenError
from app.proprietary.platforms.reddit import RedditAccessBlockedError, RedditScrapeInput

pytestmark = pytest.mark.unit


class _FakeScraper:
    """Records the actor input + limit it was called with; returns canned items."""

    def __init__(self, items: list[dict]):
        self._items = items
        self.calls: list[tuple[RedditScrapeInput, int | None]] = []

    async def __call__(
        self, actor_input: RedditScrapeInput, *, limit: int | None = None
    ) -> list[dict]:
        self.calls.append((actor_input, limit))
        return self._items


async def test_maps_urls_to_start_urls_and_wraps_items():
    scraper = _FakeScraper([{"dataType": "post", "id": "abc", "title": "Hello"}])
    execute = build_scrape_executor(scrape_fn=scraper)

    out = await execute(ScrapeInput(urls=["https://www.reddit.com/r/python/"]))

    assert isinstance(out, ScrapeOutput)
    assert len(out.items) == 1
    assert out.items[0].id == "abc"
    assert out.items[0].title == "Hello"
    assert out.items[0].dataType == "post"

    (actor_input, _limit) = scraper.calls[0]
    assert [u.url for u in actor_input.startUrls] == ["https://www.reddit.com/r/python/"]
    assert actor_input.searches == []


async def test_forwards_search_queries_and_community():
    scraper = _FakeScraper([])
    execute = build_scrape_executor(scrape_fn=scraper)

    await execute(ScrapeInput(search_queries=["a", "b"], community="python"))

    (actor_input, _limit) = scraper.calls[0]
    assert actor_input.searches == ["a", "b"]
    assert actor_input.searchCommunityName == "python"
    assert actor_input.startUrls == []


async def test_maps_caps_and_passes_limit():
    scraper = _FakeScraper([])
    execute = build_scrape_executor(scrape_fn=scraper)

    await execute(
        ScrapeInput(
            search_queries=["x"],
            max_items=25,
            max_posts=7,
            max_comments=3,
            skip_comments=True,
            sort="top",
            time_filter="week",
        )
    )

    (actor_input, limit) = scraper.calls[0]
    assert actor_input.maxItems == 25
    assert actor_input.maxPostCount == 7
    assert actor_input.maxComments == 3
    assert actor_input.skipComments is True
    assert actor_input.sort == "top"
    assert actor_input.time == "week"
    # The outer collection limit is the caller's total-item cap.
    assert limit == 25


async def test_access_blocked_maps_to_forbidden():
    async def _blocked(actor_input: RedditScrapeInput, *, limit: int | None = None):
        raise RedditAccessBlockedError("all IPs refused")

    execute = build_scrape_executor(scrape_fn=_blocked)

    with pytest.raises(ForbiddenError):
        await execute(ScrapeInput(search_queries=["x"]))
