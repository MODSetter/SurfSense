"""The registry exposes each verb as one Capability entry the doors/agent read from."""

from __future__ import annotations

import pytest

from app.capabilities import (
    web,  # noqa: F401  — importing the namespace registers its verbs
)
from app.capabilities.store import get_capability
from app.capabilities.types import BillingUnit
from app.capabilities.web.discover.schemas import DiscoverInput, DiscoverOutput
from app.capabilities.web.scrape.schemas import ScrapeInput, ScrapeOutput

pytestmark = pytest.mark.unit


def test_web_scrape_is_registered_with_its_schemas_and_billing_unit():
    cap = get_capability("web.scrape")

    assert cap.name == "web.scrape"
    assert cap.input_schema is ScrapeInput
    assert cap.output_schema is ScrapeOutput
    assert cap.billing_unit is BillingUnit.WEB_CRAWL


def test_web_discover_is_registered_and_free():
    cap = get_capability("web.discover")

    assert cap.name == "web.discover"
    assert cap.input_schema is DiscoverInput
    assert cap.output_schema is DiscoverOutput
    assert cap.billing_unit is None
