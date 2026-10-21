"""A cohort's figures as they may be shown: small cells withheld.

A count under 5, or a median of fewer than 5 values, could single out a buyer
in a week of a dozen trials, so it is ``None`` here and ``<5`` in the table.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from statistics import median
from typing import Any

from .weekly import Cohort

SMALLEST_SHOWN = 5


def published_figures(cohort: Cohort, today: date) -> dict[str, Any]:
    has_host = cohort.seen_on_host is not None
    return {
        "trials": _count(cohort.trials),
        "company": _count(cohort.company),
        "free_mail": _count(cohort.free_mail),
        "education": _count(cohort.education),
        "host_data": has_host,
        "seen_on_host": _count(cohort.seen_on_host) if has_host else None,
        "median_days_to_first_call": _median(cohort.days_to_first_call),
        "paid_30d": _count(cohort.paid_within_30),
        "paid_60d": _count(cohort.paid_within_60),
        "median_days_to_pay": _median(cohort.days_to_pay),
        "refunded": _count(cohort.refunded),
        # Some trials are too young for the window to have closed on them.
        "window_30d_open": cohort.last_day + timedelta(days=30) > today,
        "window_60d_open": cohort.last_day + timedelta(days=60) > today,
    }


def _count(value: int | None) -> int | None:
    return value if value is not None and value >= SMALLEST_SHOWN else None


def _median(values: Sequence[int]) -> float | None:
    return float(median(values)) if len(values) >= SMALLEST_SHOWN else None
