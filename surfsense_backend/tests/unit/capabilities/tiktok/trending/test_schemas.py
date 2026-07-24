"""``tiktok.trending`` input guards and billing: bounded count, ErrorItems free."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.capabilities.tiktok.scrape.schemas import MAX_TIKTOK_ITEMS
from app.capabilities.tiktok.trending.schemas import TrendingInput, TrendingOutput

pytestmark = pytest.mark.unit


def test_defaults_and_bounds():
    payload = TrendingInput()
    assert payload.max_items == 20
    assert payload.estimated_units == 20
    with pytest.raises(ValidationError):
        TrendingInput(max_items=0)
    with pytest.raises(ValidationError):
        TrendingInput(max_items=MAX_TIKTOK_ITEMS + 1)


def test_error_items_are_not_billed():
    # Real videos count; an ErrorItem (empty/withheld feed) is surfaced free.
    out = TrendingOutput(
        items=[
            {"id": "1", "webVideoUrl": "https://tiktok.com/@a/video/1"},
            {"errorCode": "no_items", "input": "explore", "error": "empty"},
        ]
    )
    assert len(out.items) == 2
    assert out.billable_units == 1
