"""Trials grouped by ISO week and joined to plugin use and to the purchase that followed."""

from __future__ import annotations

from datetime import date

import pytest

from license.cohorts.models import Purchase, Trial
from license.cohorts.weekly import ALL_WEEKS, weekly_cohorts

pytestmark = pytest.mark.unit

# Monday 12 Oct 2026 opens ISO week 42; Monday 19 Oct opens week 43.
WEEK_42 = date(2026, 10, 12)
WEEK_43 = date(2026, 10, 19)


def trial(n: int, created: date, email: str | None = None) -> Trial:
    return Trial(f"lic-{n}", created, email or f"user{n}@acme.test")


def purchase(paid_on: date, *emails: str, refunded: bool = False) -> Purchase:
    return Purchase(paid_on=paid_on, folded_emails=set(emails), refunded=refunded)


def by_label(cohorts):
    return {cohort.label: cohort for cohort in cohorts}


def test_trials_fall_into_the_iso_week_they_were_issued_in_and_a_total():
    cohorts = weekly_cohorts(
        [trial(1, WEEK_42), trial(2, date(2026, 10, 18)), trial(3, WEEK_43)], [], None
    )

    assert [c.label for c in cohorts] == ["2026-W42", "2026-W43", ALL_WEEKS]
    assert [c.trials for c in cohorts] == [2, 1, 3]
    assert cohorts[0].last_day == date(2026, 10, 18)
    assert cohorts[-1].last_day == WEEK_43


def test_a_trial_is_matched_to_the_first_purchase_from_its_address_after_it():
    cohorts = weekly_cohorts(
        [trial(1, WEEK_42, "ana@acme.test")],
        [
            purchase(date(2026, 10, 1), "ana@acme.test"),
            purchase(date(2026, 12, 1), "ana@acme.test"),
            purchase(date(2026, 11, 1), "ana@acme.test", refunded=True),
        ],
        None,
    )
    week = by_label(cohorts)["2026-W42"]

    assert week.days_to_pay == (20,)
    assert (week.paid_within_30, week.paid_within_60) == (1, 1)
    assert week.refunded == 1


def test_a_purchase_from_the_stripe_customer_address_also_counts():
    cohorts = weekly_cohorts(
        [trial(1, WEEK_42, "ana@gmail.com")],
        [purchase(date(2026, 12, 1), "billing@acme.test", "ana@gmail.com")],
        None,
    )
    week = by_label(cohorts)["2026-W42"]

    assert week.days_to_pay == (50,)
    assert (week.paid_within_30, week.paid_within_60) == (0, 1)


def test_address_kinds_are_counted_per_week():
    cohorts = weekly_cohorts(
        [
            trial(1, WEEK_42, "a@gmail.com"),
            trial(2, WEEK_42, "b@acme.test"),
            trial(3, WEEK_42, "c@mit.edu"),
            trial(4, WEEK_42, "d@acme.test"),
        ],
        [],
        None,
    )
    week = by_label(cohorts)["2026-W42"]

    assert (week.company, week.free_mail, week.education) == (2, 1, 1)


def test_plugin_host_first_calls_are_counted_in_days_from_the_trial():
    cohorts = weekly_cohorts(
        [trial(1, WEEK_42), trial(2, WEEK_42)],
        [],
        {"lic-1": date(2026, 10, 15), "lic-other": date(2026, 10, 13)},
    )
    week = by_label(cohorts)["2026-W42"]

    assert week.seen_on_host == 1
    assert week.days_to_first_call == (3,)


def test_without_plugin_host_data_plugin_use_is_unknown_not_zero():
    week = by_label(weekly_cohorts([trial(1, WEEK_42)], [], None))["2026-W42"]

    assert week.seen_on_host is None


def test_no_trials_means_no_cohorts():
    assert weekly_cohorts([], [purchase(WEEK_42, "a@acme.test")], None) == []
