"""``youtube.scrape`` executor: verb input → actor input mapping → typed items.

Boundary mocked: the proprietary scraper (injected fake). NOT mocked: the verb's
own payload→YouTubeScrapeInput mapping and the dict→VideoItem wrapping.
"""

from __future__ import annotations

import pytest

from app.capabilities.youtube.scrape.executor import build_scrape_executor
from app.capabilities.youtube.scrape.schemas import ScrapeInput, ScrapeOutput
from app.proprietary.scrapers.youtube import YouTubeScrapeInput

pytestmark = pytest.mark.unit


class _FakeScraper:
    """Records the actor input it was called with and returns canned items."""

    def __init__(self, items: list[dict]):
        self._items = items
        self.calls: list[YouTubeScrapeInput] = []

    async def __call__(self, actor_input: YouTubeScrapeInput) -> list[dict]:
        self.calls.append(actor_input)
        return self._items


async def test_maps_urls_to_start_urls_and_wraps_items():
    scraper = _FakeScraper([{"id": "abc", "title": "Hello"}])
    execute = build_scrape_executor(scrape_fn=scraper)

    out = await execute(ScrapeInput(urls=["https://www.youtube.com/watch?v=abc"]))

    assert isinstance(out, ScrapeOutput)
    assert len(out.items) == 1
    assert out.items[0].id == "abc"
    assert out.items[0].title == "Hello"

    (actor_input,) = scraper.calls
    assert [u.url for u in actor_input.startUrls] == [
        "https://www.youtube.com/watch?v=abc"
    ]
    assert actor_input.searchQueries == []


async def test_forwards_search_queries():
    scraper = _FakeScraper([])
    execute = build_scrape_executor(scrape_fn=scraper)

    await execute(ScrapeInput(search_queries=["python", "rust"]))

    (actor_input,) = scraper.calls
    assert actor_input.searchQueries == ["python", "rust"]
    assert actor_input.startUrls == []


async def test_max_results_caps_every_content_type():
    scraper = _FakeScraper([])
    execute = build_scrape_executor(scrape_fn=scraper)

    await execute(ScrapeInput(search_queries=["x"], max_results=7))

    (actor_input,) = scraper.calls
    # Videos, shorts, and streams must all inherit the caller's cap, otherwise a
    # channel scrape would silently return only plain videos (actor default 0).
    assert actor_input.maxResults == 7
    assert actor_input.maxResultsShorts == 7
    assert actor_input.maxResultStreams == 7


async def test_forwards_subtitle_options():
    scraper = _FakeScraper([])
    execute = build_scrape_executor(scrape_fn=scraper)

    await execute(
        ScrapeInput(
            urls=["https://youtu.be/abc"],
            download_subtitles=True,
            subtitles_language="fr",
        )
    )

    (actor_input,) = scraper.calls
    assert actor_input.downloadSubtitles is True
    assert actor_input.subtitlesLanguage == "fr"
