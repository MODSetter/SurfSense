"""What leaves the report: small cells withheld, open windows marked, no identifiers."""

from __future__ import annotations

from datetime import date

import pytest

from app.license.cohorts.markdown_table import render_table
from app.license.cohorts.posthog_events import DISTINCT_ID, EVENT, send_cohort_events
from app.license.cohorts.published_figures import published_figures
from app.license.cohorts.weekly import Cohort

pytestmark = pytest.mark.unit

TODAY = date(2026, 12, 31)


def cohort(**overrides) -> Cohort:
    figures = {
        "label": "2026-W42",
        "last_day": date(2026, 10, 18),
        "trials": 40,
        "company": 10,
        "free_mail": 26,
        "education": 4,
        "seen_on_host": 12,
        "days_to_first_call": (0, 1, 1, 2, 9),
        "paid_within_30": 5,
        "paid_within_60": 6,
        "days_to_pay": (3, 8, 11, 20, 25, 41),
        "refunded": 0,
    }
    figures.update(overrides)
    return Cohort(**figures)


def test_counts_and_medians_under_five_are_withheld():
    figures = published_figures(cohort(), TODAY)

    assert figures["trials"] == 40
    assert figures["education"] is None
    assert figures["refunded"] is None
    assert figures["median_days_to_first_call"] == 1.0
    assert figures["median_days_to_pay"] == 15.5
    sparse = published_figures(cohort(days_to_pay=(3, 8)), TODAY)
    assert sparse["median_days_to_pay"] is None


def test_a_lone_withheld_kind_takes_the_smallest_other_kind_with_it():
    # Otherwise the trials less the two shown kinds would give the withheld one.
    figures = published_figures(cohort(), TODAY)

    kinds = (figures["company"], figures["free_mail"], figures["education"])
    assert kinds == (None, 26, None)
    assert figures["withheld_to_protect"] == ["company"]


def test_two_withheld_kinds_withhold_no_third():
    figures = published_figures(cohort(company=34, free_mail=3, education=3), TODAY)

    kinds = (figures["company"], figures["free_mail"], figures["education"])
    assert kinds == (34, None, None)
    assert figures["withheld_to_protect"] == []


def test_a_window_is_open_until_the_cohorts_youngest_trial_has_lived_through_it():
    figures = published_figures(cohort(), date(2026, 11, 30))

    assert figures["window_30d_open"] is False
    assert figures["window_60d_open"] is True


def test_the_table_shows_shares_and_writes_withheld_cells_as_under_five():
    table = render_table([cohort()], TODAY)
    row = table.splitlines()[2].split(" | ")

    assert row[0] == "| 2026-W42"
    assert row[1:6] == ["40", "x", "26 (65%)", "<5", "12 (30%)"]
    assert row[6:10] == ["1", "5 (12%)", "6 (15%)", "15.5"]
    assert row[10] == "<5 |"


def test_the_all_row_withholds_its_kinds_when_a_week_withholds_one():
    weeks = [cohort(), cohort(label="2026-W43", company=10, free_mail=24, education=6)]
    everyone = cohort(label="All", trials=80, company=20, free_mail=50, education=10)

    row = render_table([*weeks, everyone], TODAY).splitlines()[4].split(" | ")

    assert row[0] == "| All"
    assert row[1:5] == ["80", "x", "x", "x"]


def test_the_all_row_shows_its_kinds_when_no_week_withholds_one():
    week = cohort(company=10, free_mail=24, education=6)
    everyone = cohort(label="All", company=10, free_mail=24, education=6)

    row = render_table([week, everyone], TODAY).splitlines()[3].split(" | ")

    assert row[2:5] == ["10 (25%)", "24 (60%)", "6 (15%)"]


def test_the_table_says_plugin_use_is_unknown_without_host_data():
    row = render_table([cohort(seen_on_host=None, days_to_first_call=())], TODAY)
    cells = row.splitlines()[2].split(" | ")

    assert cells[5:7] == ["n/a", "n/a"]


def test_an_open_window_is_marked():
    row = render_table([cohort()], date(2026, 11, 1)).splitlines()[2]

    assert "5 (12%) (open)" in row
    assert "6 (15%) (open)" in row


def test_each_week_is_sent_as_one_personless_event_and_the_total_is_not():
    sent = []

    def capture(event, *, distinct_id, properties):
        sent.append((event, distinct_id, properties))

    count = send_cohort_events([cohort(), cohort(label="All")], TODAY, capture=capture)

    assert count == 1
    [(event, distinct_id, properties)] = sent
    assert (event, distinct_id) == (EVENT, DISTINCT_ID)
    assert properties["cohort_week"] == "2026-W42"
    assert properties["$process_person_profile"] is False
    assert properties["education"] is None
    assert properties["company"] is None
    assert properties["withheld_to_protect"] == ["company"]
    assert properties["paid_30d"] == 5
