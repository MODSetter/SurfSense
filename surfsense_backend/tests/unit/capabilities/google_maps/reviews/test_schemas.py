"""``google_maps.reviews`` input guards: a source is required and the batch is bounded."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.capabilities.google_maps.reviews.schemas import (
    MAX_MAPS_REVIEW_SOURCES,
    ReviewsInput,
)

pytestmark = pytest.mark.unit


def test_rejects_input_with_no_source():
    with pytest.raises(ValidationError):
        ReviewsInput()


def test_accepts_urls_or_place_ids():
    assert ReviewsInput(urls=["https://maps.google.com/x"]).place_ids == []
    assert ReviewsInput(place_ids=["ChIJx"]).urls == []


def test_max_reviews_defaults_and_is_bounded():
    assert ReviewsInput(place_ids=["ChIJx"]).max_reviews == 20
    with pytest.raises(ValidationError):
        ReviewsInput(place_ids=["ChIJx"], max_reviews=0)


def test_rejects_more_sources_than_the_cap():
    too_many = [f"ChIJ{i}" for i in range(MAX_MAPS_REVIEW_SOURCES + 1)]
    with pytest.raises(ValidationError):
        ReviewsInput(place_ids=too_many)
