"""``tiktok.comments`` input guards and billing: a video URL is required, bounded,
and ErrorItems are surfaced free."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.capabilities.tiktok.comments.schemas import CommentsInput, CommentsOutput
from app.capabilities.tiktok.scrape.schemas import MAX_TIKTOK_ITEMS, MAX_TIKTOK_SOURCES

pytestmark = pytest.mark.unit

_VIDEO = "https://www.tiktok.com/@bob/video/123"


def test_rejects_input_with_no_url():
    with pytest.raises(ValidationError):
        CommentsInput(video_urls=[])


def test_defaults_and_bounds():
    payload = CommentsInput(video_urls=[_VIDEO])
    assert payload.max_items == 20
    assert payload.comments_per_video == 20
    assert payload.estimated_units == 20
    with pytest.raises(ValidationError):
        CommentsInput(video_urls=[_VIDEO], max_items=0)
    with pytest.raises(ValidationError):
        CommentsInput(video_urls=[_VIDEO], max_items=MAX_TIKTOK_ITEMS + 1)


def test_rejects_more_urls_than_the_cap():
    too_many = [f"{_VIDEO}{i}" for i in range(MAX_TIKTOK_SOURCES + 1)]
    with pytest.raises(ValidationError):
        CommentsInput(video_urls=too_many)


def test_error_items_are_not_billed():
    # Real comments count; ErrorItems (bad URL / empty video) are surfaced free.
    out = CommentsOutput(
        items=[
            {"id": "1", "text": "hi"},
            {"errorCode": "no_comments", "input": "123", "error": "empty"},
        ]
    )
    assert len(out.items) == 2
    assert out.billable_units == 1
