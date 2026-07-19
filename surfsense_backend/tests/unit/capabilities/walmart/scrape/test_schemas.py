from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.capabilities.walmart.scrape.schemas import (
    MAX_WALMART_RESULTS,
    ScrapeInput,
    ScrapeOutput,
)


def test_estimated_units_cover_search_and_direct_sources():
    payload = ScrapeInput(
        search_terms=["air fryer", "blender"],
        urls=["https://www.walmart.com/ip/123456"],
        max_items=20,
    )

    # (2 search + 1 direct source) * 20 items each
    assert payload.estimated_units == 60


def test_estimated_units_respect_hard_run_ceiling():
    payload = ScrapeInput(search_terms=["x"] * 20, max_items=100)
    assert payload.estimated_units == MAX_WALMART_RESULTS


def test_at_least_one_source_is_required():
    with pytest.raises(ValidationError):
        ScrapeInput()


def test_combined_sources_are_capped():
    with pytest.raises(ValidationError):
        ScrapeInput(urls=["u"] * 11, search_terms=["t"] * 10)


def test_start_urls_synthesize_a_search_url_per_term():
    payload = ScrapeInput(
        urls=["https://www.walmart.com/ip/1"], search_terms=["air fryer"]
    )

    assert payload.start_urls() == [
        "https://www.walmart.com/ip/1",
        "https://www.walmart.com/search?q=air+fryer",
    ]


def test_error_items_are_not_billable():
    output = ScrapeOutput(
        items=[
            {"usItemId": "123", "name": "Product"},
            {"error": "product_not_found", "errorDescription": "Missing"},
        ]
    )

    assert output.billable_units == 1
