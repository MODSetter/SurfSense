from __future__ import annotations

from app.capabilities.amazon.scrape.schemas import ScrapeInput, ScrapeOutput
from app.capabilities.core import BillingUnit
from app.capabilities.core.store import get_capability


def test_amazon_scrape_is_registered_and_metered():
    capability = get_capability("amazon.scrape")

    assert capability.input_schema is ScrapeInput
    assert capability.output_schema is ScrapeOutput
    assert capability.billing_unit is BillingUnit.AMAZON_PRODUCT
