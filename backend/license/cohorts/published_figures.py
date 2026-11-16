"""A cohort's figures as they may be shown: small cells withheld.

A count under 5, or a median of fewer than 5 values, could single out a buyer
in a week of a dozen trials, so it is ``None`` here and ``<5`` in the table.
Other cells are withheld so that none of those can be worked out: ``None`` too,
named in ``withheld_to_protect`` and ``x`` in the table whatever their own
value, since a mark saying a cell is 5 or more would pin a small one beside it.
The kinds add up to the trials, so one under 5 withholds all three, and the All
row sums the weeks, so it withholds each column that any week withholds.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from statistics import median
from typing import Any

from .weekly import ALL_WEEKS, Cohort

SMALLEST_SHOWN = 5
KINDS = ("company", "free_mail", "education")
# The All row's figure in each of these is the sum of the weeks'.
SUMMED = ("trials", *KINDS, "seen_on_host", "paid_30d", "paid_60d", "refunded")


def published_figures(cohort: Cohort, today: date) -> dict[str, Any]:
    has_host = cohort.seen_on_host is not None
    kinds = {kind: getattr(cohort, kind) for kind in KINDS}
    small_kind = min(kinds.values()) < SMALLEST_SHOWN
    return {
        "trials": _count(cohort.trials),
        **{kind: None if small_kind else kinds[kind] for kind in KINDS},
        "withheld_to_protect": list(KINDS) if small_kind else [],
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


def published_rows(
    cohorts: list[Cohort], today: date
) -> list[tuple[str, dict[str, Any]]]:
    """Each cohort's label and figures, for a table that shows them together."""
    rows = [(cohort.label, published_figures(cohort, today)) for cohort in cohorts]
    # Plugin use without host data reads n/a, which hides nothing.
    withheld = {
        key
        for label, figures in rows
        if label != ALL_WEEKS
        for key in SUMMED
        if figures[key] is None and (key != "seen_on_host" or figures["host_data"])
    }
    for label, figures in rows:
        if label == ALL_WEEKS:
            _withhold(figures, withheld)
    return rows


def _withhold(figures: dict[str, Any], keys: set[str]) -> None:
    for key in SUMMED:
        if key in keys and key not in figures["withheld_to_protect"]:
            figures[key] = None
            figures["withheld_to_protect"].append(key)


def _count(value: int | None) -> int | None:
    return value if value is not None and value >= SMALLEST_SHOWN else None


def _median(values: Sequence[int]) -> float | None:
    return float(median(values)) if len(values) >= SMALLEST_SHOWN else None
