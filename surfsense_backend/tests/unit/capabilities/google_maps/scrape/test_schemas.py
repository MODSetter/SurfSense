"""``google_maps.scrape`` input guards: a source is required and the batch is bounded."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.capabilities.google_maps.scrape.schemas import (
    MAX_MAPS_SOURCES,
    ScrapeInput,
)

pytestmark = pytest.mark.unit


def test_rejects_input_with_no_source():
    with pytest.raises(ValidationError):
        ScrapeInput()


def test_accepts_any_single_source():
    assert ScrapeInput(search_queries=["coffee"]).urls == []
    assert ScrapeInput(urls=["https://maps.google.com/x"]).place_ids == []
    assert ScrapeInput(place_ids=["ChIJx"]).search_queries == []


def test_max_places_defaults_and_is_bounded():
    assert ScrapeInput(search_queries=["x"]).max_places == 10
    with pytest.raises(ValidationError):
        ScrapeInput(search_queries=["x"], max_places=0)


def test_rejects_more_sources_than_the_cap():
    too_many = [f"q{i}" for i in range(MAX_MAPS_SOURCES + 1)]
    with pytest.raises(ValidationError):
        ScrapeInput(search_queries=too_many)
