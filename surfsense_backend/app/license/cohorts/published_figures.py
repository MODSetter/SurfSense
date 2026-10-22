"""A cohort's figures as they may be shown: small cells withheld.

A count under 5, or a median of fewer than 5 values, could single out a buyer
in a week of a dozen trials, so it is ``None`` here and ``<5`` in the table.
The kinds add up to the trials, so a kind withheld alone could be worked out by
subtraction; another is withheld with it, ``None`` too but named in
``withheld_to_protect``, and ``x`` in the table.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from statistics import median
from typing import Any

from .weekly import ALL_WEEKS, Cohort

SMALLEST_SHOWN = 5
KINDS = ("company", "free_mail", "education")


def published_figures(cohort: Cohort, today: date) -> dict[str, Any]:
    has_host = cohort.seen_on_host is not None
    kinds = {kind: _count(getattr(cohort, kind)) for kind in KINDS}
    shown = [kind for kind in KINDS if kinds[kind] is not None]
    protect = (
        [min(shown, key=lambda kind: kinds[kind])]
        if len(shown) == len(KINDS) - 1
        else []
    )
    return {
        "trials": _count(cohort.trials),
        **{kind: None if kind in protect else kinds[kind] for kind in KINDS},
        "withheld_to_protect": protect,
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
    weeks = [figures for label, figures in rows if label != ALL_WEEKS]
    if any(figures[kind] is None for figures in weeks for kind in KINDS):
        # The All row is the weeks' sum, so its kinds would give a week's away.
        for label, figures in rows:
            if label == ALL_WEEKS:
                _withhold_kinds(figures)
    return rows


def _withhold_kinds(figures: dict[str, Any]) -> None:
    for kind in KINDS:
        if figures[kind] is not None:
            figures[kind] = None
            figures["withheld_to_protect"].append(kind)


def _count(value: int | None) -> int | None:
    return value if value is not None and value >= SMALLEST_SHOWN else None


def _median(values: Sequence[int]) -> float | None:
    return float(median(values)) if len(values) >= SMALLEST_SHOWN else None
