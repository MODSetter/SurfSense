from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.capabilities.walmart.reviews.schemas import ReviewsInput, ReviewsOutput


def test_estimated_units_scale_with_sources_and_max_reviews():
    payload = ReviewsInput(
        urls=["https://www.walmart.com/ip/1"], item_ids=["222"], max_reviews=150
    )

    # 2 sources * 150 reviews each
    assert payload.estimated_units == 300


def test_at_least_one_source_is_required():
    with pytest.raises(ValidationError):
        ReviewsInput()


def test_sources_merge_urls_then_item_ids():
    payload = ReviewsInput(urls=["https://www.walmart.com/ip/1"], item_ids=["222"])

    assert payload.sources() == ["https://www.walmart.com/ip/1", "222"]


def test_error_items_are_not_billable():
    output = ReviewsOutput(
        items=[
            {"reviewId": "r1", "rating": 5},
            {"error": "reviews_not_found"},
        ]
    )

    assert output.billable_units == 1
