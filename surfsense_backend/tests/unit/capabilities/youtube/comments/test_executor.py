"""``youtube.comments`` executor: verb input → actor input mapping → typed items."""

from __future__ import annotations

import pytest

from app.capabilities.youtube.comments.executor import build_comments_executor
from app.capabilities.youtube.comments.schemas import CommentsInput, CommentsOutput
from app.proprietary.scrapers.youtube import YouTubeCommentsInput

pytestmark = pytest.mark.unit


class _FakeScraper:
    def __init__(self, items: list[dict]):
        self._items = items
        self.calls: list[YouTubeCommentsInput] = []

    async def __call__(self, actor_input: YouTubeCommentsInput) -> list[dict]:
        self.calls.append(actor_input)
        return self._items


async def test_maps_urls_and_wraps_comment_items():
    scraper = _FakeScraper([{"cid": "c1", "comment": "nice", "author": "@a"}])
    execute = build_comments_executor(scrape_fn=scraper)

    out = await execute(CommentsInput(urls=["https://www.youtube.com/watch?v=abc"]))

    assert isinstance(out, CommentsOutput)
    assert len(out.items) == 1
    assert out.items[0].cid == "c1"
    assert out.items[0].comment == "nice"

    (actor_input,) = scraper.calls
    assert [u.url for u in actor_input.startUrls] == [
        "https://www.youtube.com/watch?v=abc"
    ]


async def test_forwards_max_comments_and_sort():
    scraper = _FakeScraper([])
    execute = build_comments_executor(scrape_fn=scraper)

    await execute(
        CommentsInput(
            urls=["https://youtu.be/abc"],
            max_comments=50,
            sort_by="TOP_COMMENTS",
        )
    )

    (actor_input,) = scraper.calls
    assert actor_input.maxComments == 50
    assert actor_input.sortCommentsBy == "TOP_COMMENTS"
