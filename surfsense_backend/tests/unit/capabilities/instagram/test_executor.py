"""Executor tests: lean verb input → ``InstagramScrapeInput`` mapping + wrapping.

A fake scraper captures the actor input the executor built (no network), so the
snake_case→camelCase mapping and the ``InstagramAccessBlockedError`` →
``ForbiddenError`` translation are asserted deterministically.
"""

from __future__ import annotations

import pytest

from app.capabilities.instagram.comments.executor import build_comments_executor
from app.capabilities.instagram.comments.schemas import CommentsInput, CommentsOutput
from app.capabilities.instagram.details.executor import build_details_executor
from app.capabilities.instagram.details.schemas import DetailsInput, DetailsOutput
from app.capabilities.instagram.scrape.executor import build_scrape_executor
from app.capabilities.instagram.scrape.schemas import ScrapeInput, ScrapeOutput
from app.exceptions import ForbiddenError
from app.proprietary.platforms.instagram import (
    InstagramAccessBlockedError,
    InstagramScrapeInput,
)

pytestmark = pytest.mark.unit


class _FakeScraper:
    def __init__(self, items: list[dict]) -> None:
        self.items = items
        self.calls: list[tuple[InstagramScrapeInput, int | None]] = []

    async def __call__(self, actor_input, *, limit=None):
        self.calls.append((actor_input, limit))
        return self.items


async def test_scrape_maps_urls_and_wraps_items():
    fake = _FakeScraper([{"id": "1", "shortCode": "abc", "caption": "hi"}])
    execute = build_scrape_executor(fake)
    out = await execute(ScrapeInput(urls=["https://www.instagram.com/natgeo/"]))
    assert isinstance(out, ScrapeOutput)
    assert out.items[0].shortCode == "abc"
    actor_input, limit = fake.calls[0]
    assert actor_input.resultsType == "posts"
    assert actor_input.directUrls == ["https://www.instagram.com/natgeo/"]
    assert actor_input.search == ""
    assert limit == 10  # default max_items forwarded as the collector limit


async def test_scrape_joins_search_queries():
    fake = _FakeScraper([])
    execute = build_scrape_executor(fake)
    await execute(ScrapeInput(search_queries=["fit", "gym"], search_type="hashtag"))
    actor_input, _ = fake.calls[0]
    assert actor_input.search == "fit,gym"
    assert actor_input.searchType == "hashtag"
    assert actor_input.directUrls == []


async def test_scrape_access_blocked_maps_to_forbidden():
    async def _blocked(actor_input, *, limit=None):
        raise InstagramAccessBlockedError("login wall")

    execute = build_scrape_executor(_blocked)
    with pytest.raises(ForbiddenError):
        await execute(ScrapeInput(urls=["x"]))


async def test_comments_maps_flags():
    fake = _FakeScraper([{"id": "c1", "text": "nice"}])
    execute = build_comments_executor(fake)
    out = await execute(
        CommentsInput(
            urls=["https://www.instagram.com/p/Cabc/"],
            newest_first=True,
            include_replies=True,
            max_comments_per_post=25,
        )
    )
    assert isinstance(out, CommentsOutput)
    assert out.items[0].text == "nice"
    actor_input, _ = fake.calls[0]
    assert actor_input.resultsType == "comments"
    assert actor_input.isNewestComments is True
    assert actor_input.includeNestedComments is True
    assert actor_input.resultsLimit == 25


async def test_details_maps_and_wraps_discriminated_items():
    fake = _FakeScraper(
        [
            {
                "detailKind": "profile",
                "username": "natgeo",
                "url": "https://www.instagram.com/natgeo/",
            }
        ]
    )
    execute = build_details_executor(fake)
    out = await execute(DetailsInput(urls=["https://www.instagram.com/natgeo/"]))
    assert isinstance(out, DetailsOutput)
    assert out.items[0].username == "natgeo"
    actor_input, _ = fake.calls[0]
    assert actor_input.resultsType == "details"
