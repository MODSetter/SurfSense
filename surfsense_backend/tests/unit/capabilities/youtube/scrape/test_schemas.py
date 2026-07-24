"""``youtube.scrape`` input guards: a source is required and the batch is bounded."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.capabilities.youtube.scrape.schemas import (
    MAX_YOUTUBE_SOURCES,
    ScrapeInput,
)

pytestmark = pytest.mark.unit


def test_rejects_input_with_neither_urls_nor_queries():
    with pytest.raises(ValidationError):
        ScrapeInput()


def test_accepts_urls_only():
    payload = ScrapeInput(urls=["https://www.youtube.com/watch?v=abc"])
    assert payload.search_queries == []


def test_accepts_search_queries_only():
    payload = ScrapeInput(search_queries=["python tutorial"])
    assert payload.urls == []


def test_max_results_defaults_and_is_bounded():
    assert ScrapeInput(search_queries=["x"]).max_results == 10
    with pytest.raises(ValidationError):
        ScrapeInput(search_queries=["x"], max_results=0)


def test_rejects_more_sources_than_the_cap():
    too_many = [f"https://youtu.be/{i}" for i in range(MAX_YOUTUBE_SOURCES + 1)]
    with pytest.raises(ValidationError):
        ScrapeInput(urls=too_many)
