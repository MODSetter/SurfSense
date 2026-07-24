"""``reddit.scrape`` input guards: a source is required and the batch is bounded."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.capabilities.reddit.scrape.schemas import (
    MAX_REDDIT_ITEMS,
    MAX_REDDIT_SOURCES,
    ScrapeInput,
)

pytestmark = pytest.mark.unit


def test_rejects_input_with_no_source():
    with pytest.raises(ValidationError):
        ScrapeInput()


def test_accepts_urls_only():
    payload = ScrapeInput(urls=["https://www.reddit.com/r/python/"])
    assert payload.search_queries == []


def test_accepts_search_queries_only():
    payload = ScrapeInput(search_queries=["notebooklm alternative"])
    assert payload.urls == []


def test_accepts_community_only():
    payload = ScrapeInput(community="python")
    assert payload.community == "python"


def test_defaults_and_bounds():
    payload = ScrapeInput(search_queries=["x"])
    assert payload.max_items == 10
    assert payload.sort == "new"
    assert payload.include_nsfw is True
    with pytest.raises(ValidationError):
        ScrapeInput(search_queries=["x"], max_items=0)
    with pytest.raises(ValidationError):
        ScrapeInput(search_queries=["x"], max_items=MAX_REDDIT_ITEMS + 1)


def test_rejects_more_sources_than_the_cap():
    too_many = [f"https://redd.it/{i}" for i in range(MAX_REDDIT_SOURCES + 1)]
    with pytest.raises(ValidationError):
        ScrapeInput(urls=too_many)
