"""ScrapeOutput reports its own billable count; ScrapeInput bounds its batch size."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.capabilities.web.scrape.schemas import (
    MAX_SCRAPE_URLS,
    ScrapeInput,
    ScrapeOutput,
    ScrapeRow,
)

pytestmark = pytest.mark.unit


def _output(*statuses: str) -> ScrapeOutput:
    return ScrapeOutput(
        rows=[
            ScrapeRow(url=f"https://{i}.com", status=status)
            for i, status in enumerate(statuses)
        ]
    )


def test_billable_units_counts_successful_rows():
    assert _output("success", "empty", "success", "failed").billable_units == 2


def test_billable_units_is_zero_without_successes():
    assert _output("empty", "failed").billable_units == 0


def test_rejects_empty_url_batch():
    with pytest.raises(ValidationError):
        ScrapeInput(urls=[])


def test_rejects_batch_over_the_cap():
    with pytest.raises(ValidationError):
        ScrapeInput(urls=[f"https://{i}.com" for i in range(MAX_SCRAPE_URLS + 1)])


def test_accepts_batch_at_the_cap():
    payload = ScrapeInput(urls=[f"https://{i}.com" for i in range(MAX_SCRAPE_URLS)])
    assert payload.estimated_units == MAX_SCRAPE_URLS
