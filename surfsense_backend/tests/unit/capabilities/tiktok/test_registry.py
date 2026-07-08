"""The tiktok namespace registers its verb as one Capability the doors/agent read."""

from __future__ import annotations

import pytest

from app.capabilities import (
    tiktok,  # noqa: F401  — importing the namespace registers its verbs
)
from app.capabilities.core import BillingUnit
from app.capabilities.core.store import get_capability
from app.capabilities.tiktok.scrape.schemas import ScrapeInput, ScrapeOutput

pytestmark = pytest.mark.unit


def test_tiktok_scrape_is_registered_and_billed_per_video():
    cap = get_capability("tiktok.scrape")

    assert cap.name == "tiktok.scrape"
    assert cap.input_schema is ScrapeInput
    assert cap.output_schema is ScrapeOutput
    assert cap.billing_unit is BillingUnit.TIKTOK_VIDEO
