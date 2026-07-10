"""``tiktok.user_search`` input guards and billing: a query is required, bounded,
and ErrorItems are surfaced free."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.capabilities.tiktok.scrape.schemas import MAX_TIKTOK_ITEMS, MAX_TIKTOK_SOURCES
from app.capabilities.tiktok.user_search.schemas import (
    UserSearchInput,
    UserSearchOutput,
)

pytestmark = pytest.mark.unit


def test_rejects_input_with_no_query():
    with pytest.raises(ValidationError):
        UserSearchInput(queries=[])


def test_defaults_and_bounds():
    payload = UserSearchInput(queries=["nasa"])
    assert payload.max_items == 10
    assert payload.results_per_query == 10
    assert payload.estimated_units == 10
    with pytest.raises(ValidationError):
        UserSearchInput(queries=["nasa"], max_items=0)
    with pytest.raises(ValidationError):
        UserSearchInput(queries=["nasa"], max_items=MAX_TIKTOK_ITEMS + 1)


def test_rejects_more_queries_than_the_cap():
    too_many = [f"q{i}" for i in range(MAX_TIKTOK_SOURCES + 1)]
    with pytest.raises(ValidationError):
        UserSearchInput(queries=too_many)


def test_error_items_are_not_billed():
    # Real accounts count; ErrorItems (empty/withheld queries) are surfaced free.
    out = UserSearchOutput(
        items=[
            {"id": "1", "name": "nasa"},
            {"errorCode": "no_users", "input": "ghost", "error": "empty"},
        ]
    )
    assert len(out.items) == 2
    assert out.billable_units == 1
