from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.capabilities.amazon.scrape.schemas import (
    MAX_AMAZON_RESULTS,
    ScrapeInput,
    ScrapeOutput,
)


def test_estimated_units_cover_search_and_direct_variant_fanout():
    payload = ScrapeInput(
        search_terms=["mouse", "keyboard"],
        urls=["https://www.amazon.com/dp/B09V3KXJPB"],
        max_items=20,
        max_variants=3,
    )

    assert payload.estimated_units == 44


def test_estimated_units_respect_hard_run_ceiling():
    payload = ScrapeInput(search_terms=["x"] * 20, max_items=100)
    assert payload.estimated_units == MAX_AMAZON_RESULTS


def test_at_least_one_source_is_required():
    with pytest.raises(ValidationError):
        ScrapeInput()


def test_error_items_are_not_billable():
    output = ScrapeOutput(
        items=[
            {"asin": "B09V3KXJPB", "title": "Product"},
            {"error": "product_not_found", "errorDescription": "Missing"},
        ]
    )

    assert output.billable_units == 1
