"""One personless ``license_cohort_weekly`` event per week, from published figures."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from license import analytics as ph_analytics

from .published_figures import published_figures
from .weekly import ALL_WEEKS, Cohort

EVENT = "license_cohort_weekly"
# Personless events still need a distinct id; one constant keeps them off every
# person profile.
DISTINCT_ID = "license-cohort-report"

Capture = Callable[..., None]


def send_cohort_events(
    cohorts: list[Cohort],
    today: date,
    capture: Capture | None = None,
) -> int:
    """Returns how many were queued. Each run re-sends every week; read the latest."""
    capture = capture or ph_analytics.capture
    sent = 0
    for cohort in cohorts:
        if cohort.label == ALL_WEEKS:
            continue
        properties: dict[str, Any] = {
            "cohort_week": cohort.label,
            "report_date": today.isoformat(),
            **published_figures(cohort, today),
            "$process_person_profile": False,
        }
        capture(EVENT, distinct_id=DISTINCT_ID, properties=properties)
        sent += 1
    return sent
