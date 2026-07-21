from __future__ import annotations

from app.capabilities.core import BillingUnit
from app.capabilities.core.store import get_capability
from app.capabilities.walmart.reviews.schemas import ReviewsInput, ReviewsOutput
from app.capabilities.walmart.scrape.schemas import ScrapeInput, ScrapeOutput


def test_walmart_scrape_is_registered_and_metered():
    capability = get_capability("walmart.scrape")

    assert capability.input_schema is ScrapeInput
    assert capability.output_schema is ScrapeOutput
    assert capability.billing_unit is BillingUnit.WALMART_PRODUCT


def test_walmart_reviews_is_registered_and_metered():
    capability = get_capability("walmart.reviews")

    assert capability.input_schema is ReviewsInput
    assert capability.output_schema is ReviewsOutput
    assert capability.billing_unit is BillingUnit.WALMART_REVIEW
