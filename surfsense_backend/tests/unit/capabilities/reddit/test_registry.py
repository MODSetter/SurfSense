"""The reddit namespace registers its verb as one Capability the doors/agent read."""

from __future__ import annotations

import pytest

from app.capabilities import (
    reddit,  # noqa: F401  — importing the namespace registers its verbs
)
from app.capabilities.core.store import get_capability
from app.capabilities.reddit.scrape.schemas import ScrapeInput, ScrapeOutput

pytestmark = pytest.mark.unit


def test_reddit_scrape_is_registered_and_free():
    cap = get_capability("reddit.scrape")

    assert cap.name == "reddit.scrape"
    assert cap.input_schema is ScrapeInput
    assert cap.output_schema is ScrapeOutput
    assert cap.billing_unit is None
