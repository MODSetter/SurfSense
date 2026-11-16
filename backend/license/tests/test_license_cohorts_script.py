"""The cohort report prints aggregates only, whatever the sources hold."""

from __future__ import annotations

from datetime import date

import pytest

from license.cohorts.models import Purchase, Trial
from license.scripts import license_cohorts as report

pytestmark = pytest.mark.unit

ADDRESSES = [f"buyer{n}@acme-{n}.test" for n in range(7)]
LICENCE_IDS = [f"7c1d2e3f-0000-4000-8000-00000000000{n}" for n in range(7)]


@pytest.fixture
def sources(monkeypatch):
    """Seven trials in one week, one bought ten days in; no Stripe, no host."""
    trials = [
        Trial(licence_id, date(2026, 10, 12), address)
        for licence_id, address in zip(LICENCE_IDS, ADDRESSES, strict=True)
    ]
    purchases = [
        Purchase(date(2026, 10, 22), {ADDRESSES[0]}, checkout_session_id="cs_secret")
    ]

    async def read_licences():
        return trials, purchases

    monkeypatch.setattr(report, "read_licences", read_licences)
    monkeypatch.setattr(report.config, "STRIPE_SECRET_KEY", None)
    monkeypatch.delenv("PLUGIN_HOST_ADMIN_URL", raising=False)
    monkeypatch.delenv("USAGE_ADMIN_TOKEN", raising=False)


async def test_the_report_prints_no_address_domain_or_licence_id(sources, capsys):
    assert await report.main([]) == 0
    out = capsys.readouterr().out

    for identifier in [*ADDRESSES, *LICENCE_IDS, "acme-0.test", "cs_secret"]:
        assert identifier not in out
    week_row = next(line for line in out.splitlines() if line.startswith("| 2026-W42"))
    # No free-mail or school address, so the kinds are withheld together.
    assert week_row.split(" | ")[1:3] == ["7", "x"]
    # One purchase among seven trials is a cell under five.
    assert week_row.split(" | ")[7].startswith("<5")
    assert "Plugin host: not configured" in out


async def test_posthog_needs_a_key_before_anything_is_read(monkeypatch, capsys):
    async def read_licences():
        pytest.fail("Keygen must not be read when the run cannot finish")

    monkeypatch.setattr(report, "read_licences", read_licences)
    monkeypatch.setattr(report.ph_analytics, "is_enabled", lambda: False)

    assert await report.main(["--posthog"]) == 2
    assert "POSTHOG_API_KEY" in capsys.readouterr().err


async def test_posthog_gets_one_personless_event_per_week_and_is_flushed(
    sources, monkeypatch, capsys
):
    captured, flushed = [], []
    monkeypatch.setattr(report.ph_analytics, "is_enabled", lambda: True)
    monkeypatch.setattr(
        report.ph_analytics,
        "capture",
        lambda event, *, distinct_id, properties: captured.append(properties),
    )
    monkeypatch.setattr(report.ph_analytics, "shutdown", lambda: flushed.append(True))

    assert await report.main(["--posthog"]) == 0

    [properties] = captured
    assert properties["cohort_week"] == "2026-W42"
    assert properties["paid_30d"] is None
    assert flushed == [True]
    assert not any(
        identifier in str(properties) for identifier in [*ADDRESSES, *LICENCE_IDS]
    )
