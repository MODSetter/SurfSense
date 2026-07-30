"""Offline tests: a bare ``community`` scrapes its subreddit listing.

No network: ``_subreddit_flow`` is faked. Guards the capability-schema promise
that a community with no urls/searches scrapes its listing (regression for the
orchestrator dropping community-only input), and that the name is normalized at
the trust boundary ("r/x", "/r/x/", " x " -> "x") so it never becomes ``r/r/x``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from app.proprietary.platforms.reddit import scraper
from app.proprietary.platforms.reddit.schemas import RedditScrapeInput


def _fake_subreddit_flow(seen: list[str]):
    """Record the subreddit it's called with; yield a community + one post."""

    def flow(
        subreddit: str,
        *,
        input_model: RedditScrapeInput,
        sort: str | None = None,
    ) -> AsyncIterator[dict]:
        seen.append(subreddit)

        async def gen() -> AsyncIterator[dict]:
            yield {"dataType": "community", "id": subreddit}
            yield {"dataType": "post", "id": f"{subreddit}-p1", "title": "t"}

        return gen()

    return flow


async def test_community_only_scrapes_listing(monkeypatch):
    seen: list[str] = []
    monkeypatch.setattr(scraper, "_subreddit_flow", _fake_subreddit_flow(seen))

    model = RedditScrapeInput(searchCommunityName="movies", maxItems=10)
    items = await scraper.scrape_reddit(model, limit=10)

    assert seen == ["movies"]
    assert [i["id"] for i in items] == ["movies", "movies-p1"]


@pytest.mark.parametrize(
    "raw", ["movies", "r/movies", "/r/movies/", " movies ", "R/movies"]
)
async def test_community_name_normalized(monkeypatch, raw):
    seen: list[str] = []
    monkeypatch.setattr(scraper, "_subreddit_flow", _fake_subreddit_flow(seen))

    model = RedditScrapeInput(searchCommunityName=raw, maxItems=5)
    await scraper.scrape_reddit(model, limit=5)

    assert seen == ["movies"]


async def test_searches_present_keeps_community_as_scope(monkeypatch):
    """With searches, the name stays a search scope (community-only branch skipped)."""
    sub_seen: list[str] = []
    monkeypatch.setattr(scraper, "_subreddit_flow", _fake_subreddit_flow(sub_seen))

    scoped: list[str | None] = []

    def fake_search_flow(query, *, input_model, subreddit=None, max_items=None):
        scoped.append(subreddit)

        async def gen() -> AsyncIterator[dict]:
            yield {"dataType": "post", "id": f"{query}-1", "title": query}

        return gen()

    monkeypatch.setattr(scraper, "_search_flow", fake_search_flow)

    model = RedditScrapeInput(searches=["tempo"], searchCommunityName="r/movies")
    items = await scraper.scrape_reddit(model, limit=10)

    assert sub_seen == []  # community-only flow NOT taken
    assert scoped == ["movies"]  # normalized name used as the search scope
    assert [i["id"] for i in items] == ["tempo-1"]
