"""The google_maps namespace registers each verb as one Capability the doors/agent read."""

from __future__ import annotations

import pytest

from app.capabilities import (
    google_maps,  # noqa: F401  — importing the namespace registers its verbs
)
from app.capabilities.core import BillingUnit
from app.capabilities.core.store import get_capability
from app.capabilities.google_maps.reviews.schemas import ReviewsInput, ReviewsOutput
from app.capabilities.google_maps.scrape.schemas import ScrapeInput, ScrapeOutput

pytestmark = pytest.mark.unit


def test_google_maps_scrape_is_registered_and_billable():
    cap = get_capability("google_maps.scrape")

    assert cap.name == "google_maps.scrape"
    assert cap.input_schema is ScrapeInput
    assert cap.output_schema is ScrapeOutput
    assert cap.billing_unit is BillingUnit.GOOGLE_MAPS_PLACE


def test_google_maps_reviews_is_registered_and_billable():
    cap = get_capability("google_maps.reviews")

    assert cap.name == "google_maps.reviews"
    assert cap.input_schema is ReviewsInput
    assert cap.output_schema is ReviewsOutput
    assert cap.billing_unit is BillingUnit.GOOGLE_MAPS_REVIEW
