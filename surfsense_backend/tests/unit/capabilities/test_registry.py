"""The registry exposes each verb as one Capability entry the doors/agent read from."""

from __future__ import annotations

import pytest

from app.capabilities import (
    web,  # noqa: F401  — importing the namespace registers its verbs
)
from app.capabilities.core.store import get_capability
from app.capabilities.core.types import BillingUnit
from app.capabilities.web.crawl.schemas import CrawlInput, CrawlOutput

pytestmark = pytest.mark.unit


def test_web_crawl_is_registered_with_its_schemas_and_billing_unit():
    cap = get_capability("web.crawl")

    assert cap.name == "web.crawl"
    assert cap.input_schema is CrawlInput
    assert cap.output_schema is CrawlOutput
    assert cap.billing_unit is BillingUnit.WEB_CRAWL
