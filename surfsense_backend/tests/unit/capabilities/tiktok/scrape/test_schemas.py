"""``tiktok.scrape`` input guards: a source is required and the batch is bounded."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.capabilities.tiktok.scrape.schemas import (
    MAX_TIKTOK_ITEMS,
    MAX_TIKTOK_SOURCES,
    ScrapeInput,
    ScrapeOutput,
)

pytestmark = pytest.mark.unit


def test_rejects_input_with_no_source():
    with pytest.raises(ValidationError):
        ScrapeInput()


def test_accepts_urls_only():
    payload = ScrapeInput(urls=["https://www.tiktok.com/@nasa"])
    assert payload.profiles == []


def test_accepts_hashtags_only():
    payload = ScrapeInput(hashtags=["food"])
    assert payload.hashtags == ["food"]


def test_defaults_and_bounds():
    payload = ScrapeInput(hashtags=["food"])
    assert payload.max_items == 10
    assert payload.results_per_page == 10
    with pytest.raises(ValidationError):
        ScrapeInput(hashtags=["food"], max_items=0)
    with pytest.raises(ValidationError):
        ScrapeInput(hashtags=["food"], max_items=MAX_TIKTOK_ITEMS + 1)


def test_rejects_more_sources_than_the_cap():
    too_many = [f"tag{i}" for i in range(MAX_TIKTOK_SOURCES + 1)]
    with pytest.raises(ValidationError):
        ScrapeInput(hashtags=too_many)


def test_error_items_are_not_billed():
    # Real videos count; ErrorItems (blocked/empty targets) are surfaced free.
    out = ScrapeOutput(
        items=[
            {"id": "1", "webVideoUrl": "https://tiktok.com/@a/video/1"},
            {"errorCode": "no_items", "input": "nasa", "error": "blocked"},
        ]
    )
    assert len(out.items) == 2
    assert out.billable_units == 1
