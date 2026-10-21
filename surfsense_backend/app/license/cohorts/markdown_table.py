"""The cohorts as a markdown table, from their published figures only."""

from __future__ import annotations

from datetime import date
from typing import Any

from .published_figures import published_figures
from .weekly import Cohort

_HEADER = (
    "Week",
    "Trials",
    "Company",
    "Free mail",
    "Education",
    "Used a plugin",
    "Days to 1st call",
    "Paid ≤30 d",
    "Paid ≤60 d",
    "Days to pay",
    "Refunded",
)

LEGEND = (
    '"<5": fewer than 5, withheld. "n<5": a median of fewer than 5 values, '
    'withheld. "(open)": some trials in the row are younger than the window. '
    '"n/a": no plugin host data. Shares are of the row\'s trials.'
)


def render_table(cohorts: list[Cohort], today: date) -> str:
    lines = [_row(_HEADER), _row(tuple("---" for _ in _HEADER))]
    for cohort in cohorts:
        lines.append(_row(_cells(cohort.label, published_figures(cohort, today))))
    return "\n".join(lines)


def _cells(label: str, figures: dict[str, Any]) -> tuple[str, ...]:
    trials = figures["trials"]

    def share(key: str) -> str:
        return _share(figures[key], trials)

    def paid(key: str, window: str) -> str:
        return share(key) + (" (open)" if figures[window] else "")

    return (
        label,
        _count(trials),
        share("company"),
        share("free_mail"),
        share("education"),
        share("seen_on_host") if figures["host_data"] else "n/a",
        _median(figures["median_days_to_first_call"])
        if figures["host_data"]
        else "n/a",
        paid("paid_30d", "window_30d_open"),
        paid("paid_60d", "window_60d_open"),
        _median(figures["median_days_to_pay"]),
        _count(figures["refunded"]),
    )


def _count(value: int | None) -> str:
    return "<5" if value is None else str(value)


def _share(value: int | None, trials: int | None) -> str:
    if value is None:
        return "<5"
    if not trials:
        return str(value)
    return f"{value} ({value / trials:.0%})"


def _median(value: float | None) -> str:
    if value is None:
        return "n<5"
    return str(int(value)) if value.is_integer() else f"{value:.1f}"


def _row(cells: tuple[str, ...]) -> str:
    return "| " + " | ".join(cells) + " |"
