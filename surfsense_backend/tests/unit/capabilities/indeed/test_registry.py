"""The indeed namespace registers its verb as one Capability the doors/agent read."""

from __future__ import annotations

import pytest

from app.capabilities import (
    indeed,  # noqa: F401  — importing the namespace registers its verbs
)
from app.capabilities.core.store import get_capability
from app.capabilities.core.types import BillingUnit
from app.capabilities.indeed.scrape.schemas import ScrapeInput, ScrapeOutput

pytestmark = pytest.mark.unit


def test_indeed_scrape_is_registered_and_billed_per_job():
    cap = get_capability("indeed.scrape")

    assert cap.name == "indeed.scrape"
    assert cap.input_schema is ScrapeInput
    assert cap.output_schema is ScrapeOutput
    assert cap.billing_unit is BillingUnit.INDEED_JOB
