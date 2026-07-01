"""ScrapeOutput reports its own billable count (a success single-sources it)."""

from __future__ import annotations

import pytest

from app.capabilities.web.scrape.schemas import ScrapeOutput, ScrapeRow

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
