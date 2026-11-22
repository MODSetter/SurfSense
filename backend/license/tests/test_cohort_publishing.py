"""What leaves the report: small cells withheld, open windows marked, no identifiers."""

from __future__ import annotations

from datetime import date

import pytest

from license.cohorts.markdown_table import render_table
from license.cohorts.posthog_events import DISTINCT_ID, EVENT, send_cohort_events
from license.cohorts.published_figures import published_figures
from license.cohorts.weekly import Cohort

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


def test_a_kind_under_five_withholds_all_three_kinds():
    figures = published_figures(cohort(), TODAY)

    kinds = (figures["company"], figures["free_mail"], figures["education"])
    assert kinds == (None, None, None)
    assert figures["withheld_to_protect"] == ["company", "free_mail", "education"]


@pytest.mark.parametrize(
    ("trials", "company", "free_mail", "education"),
    [
        # 40 - 32 leaves 8 for two kinds under 5: both 4.
        (40, 4, 32, 4),
        # Three kinds under 5 in 12 trials: all 4.
        (12, 4, 4, 4),
        # 25 - 20 leaves 5; a mark saying free mail is 5 or more pins both.
        (25, 0, 5, 20),
    ],
)
def test_no_kind_under_five_can_be_worked_out_from_the_row(
    trials, company, free_mail, education
):
    week = cohort(
        trials=trials, company=company, free_mail=free_mail, education=education
    )

    row = render_table([week], TODAY).splitlines()[2].split(" | ")

    assert row[1] == str(trials)
    assert row[2:5] == ["x", "x", "x"]


def test_a_window_is_open_until_the_cohorts_youngest_trial_has_lived_through_it():
    figures = published_figures(cohort(), date(2026, 11, 30))

    assert figures["window_30d_open"] is False
    assert figures["window_60d_open"] is True


def test_the_table_shows_shares_and_writes_withheld_cells_as_under_five():
    table = render_table([cohort()], TODAY)
    row = table.splitlines()[2].split(" | ")

    assert row[0] == "| 2026-W42"
    assert row[1:6] == ["40", "x", "x", "x", "12 (30%)"]
    assert row[6:10] == ["1", "5 (12%)", "6 (15%)", "15.5"]
    assert row[10] == "<5 |"


def test_the_all_row_withholds_its_kinds_when_a_week_withholds_one():
    weeks = [cohort(), cohort(label="2026-W43", company=10, free_mail=24, education=6)]
    everyone = cohort(label="All", trials=80, company=20, free_mail=50, education=10)

    row = render_table([*weeks, everyone], TODAY).splitlines()[4].split(" | ")

    assert row[0] == "| All"
    assert row[1:5] == ["80", "x", "x", "x"]


def test_the_all_row_withholds_every_column_a_week_withholds():
    # W43's 2 buyers would be All's 8 less W42's 6.
    w42 = cohort(company=10, free_mail=24, education=6, paid_within_30=6)
    w43 = cohort(
        label="2026-W43",
        trials=4,
        company=0,
        free_mail=4,
        education=0,
        paid_within_30=2,
        paid_within_60=2,
    )
    everyone = cohort(
        label="All",
        trials=44,
        company=10,
        free_mail=28,
        education=6,
        paid_within_30=8,
        paid_within_60=8,
    )

    row = render_table([w42, w43, everyone], TODAY).splitlines()[4].split(" | ")

    assert row[0] == "| All"
    assert row[1:5] == ["x", "x", "x", "x"]
    # Plugin use is 12 in every row, so no week withholds it.
    assert row[5] == "12"
    assert row[7:9] == ["x", "x"]
    # Refunds are 0 in every row; x says nothing of the All row's own count.
    assert row[10] == "x |"


def test_the_all_row_shows_its_kinds_when_no_week_withholds_one():
    week = cohort(company=10, free_mail=24, education=6)
    everyone = cohort(label="All", company=10, free_mail=24, education=6)

    row = render_table([week, everyone], TODAY).splitlines()[3].split(" | ")

    assert row[2:5] == ["10 (25%)", "24 (60%)", "6 (15%)"]


def test_the_table_says_plugin_use_is_unknown_without_host_data():
    no_host = {"seen_on_host": None, "days_to_first_call": ()}
    weeks = [cohort(**no_host), cohort(label="All", **no_host)]

    for row in render_table(weeks, TODAY).splitlines()[2:]:
        assert row.split(" | ")[5:7] == ["n/a", "n/a"]


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
    assert properties["free_mail"] is None
    assert properties["withheld_to_protect"] == ["company", "free_mail", "education"]
    assert properties["paid_30d"] == 5
