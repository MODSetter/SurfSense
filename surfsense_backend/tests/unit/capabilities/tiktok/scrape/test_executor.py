"""``tiktok.scrape`` executor: verb input → actor input mapping → typed items.

Boundary mocked: the proprietary scraper (injected fake). NOT mocked: the verb's
own payload→TikTokScrapeInput mapping and the dict→TikTokVideoItem wrapping.
"""

from __future__ import annotations

import pytest

from app.capabilities.tiktok.scrape.executor import build_scrape_executor
from app.capabilities.tiktok.scrape.schemas import ScrapeInput, ScrapeOutput
from app.exceptions import ForbiddenError
from app.proprietary.platforms.tiktok import TikTokAccessBlockedError, TikTokScrapeInput

pytestmark = pytest.mark.unit


class _FakeScraper:
    """Records the actor input + limit it was called with; returns canned items."""

    def __init__(self, items: list[dict]):
        self._items = items
        self.calls: list[tuple[TikTokScrapeInput, int | None]] = []

    async def __call__(
        self, actor_input: TikTokScrapeInput, *, limit: int | None = None
    ) -> list[dict]:
        self.calls.append((actor_input, limit))
        return self._items


async def test_maps_urls_to_start_urls_and_wraps_items():
    scraper = _FakeScraper([{"id": "123", "text": "hello"}])
    execute = build_scrape_executor(scrape_fn=scraper)

    out = await execute(ScrapeInput(urls=["https://www.tiktok.com/@nasa/video/123"]))

    assert isinstance(out, ScrapeOutput)
    assert len(out.items) == 1
    assert out.items[0].id == "123"

    (actor_input, _limit) = scraper.calls[0]
    assert [u.url for u in actor_input.startUrls] == [
        "https://www.tiktok.com/@nasa/video/123"
    ]


async def test_forwards_typed_sources_and_limit():
    scraper = _FakeScraper([])
    execute = build_scrape_executor(scrape_fn=scraper)

    await execute(
        ScrapeInput(
            profiles=["nasa"],
            hashtags=["food"],
            results_per_page=7,
            max_items=25,
        )
    )

    (actor_input, limit) = scraper.calls[0]
    assert actor_input.profiles == ["nasa"]
    assert actor_input.hashtags == ["food"]
    assert actor_input.resultsPerPage == 7
    # The outer collection limit is the caller's total-item cap.
    assert limit == 25


async def test_access_blocked_maps_to_forbidden():
    async def _blocked(actor_input: TikTokScrapeInput, *, limit: int | None = None):
        raise TikTokAccessBlockedError("all IPs refused")

    execute = build_scrape_executor(scrape_fn=_blocked)

    with pytest.raises(ForbiddenError):
        await execute(ScrapeInput(hashtags=["food"]))
