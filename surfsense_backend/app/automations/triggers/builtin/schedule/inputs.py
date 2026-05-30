"""Build run inputs from a schedule fire."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def schedule_runtime_inputs(
    *,
    fired_at: datetime,
    scheduled_for: datetime,
    previous_last_fired_at: datetime | None,
) -> dict[str, Any]:
    """Calendar context for a scheduled run.

    - ``fired_at`` — actual fire time
    - ``scheduled_for`` — cron-derived target time for this fire
    - ``last_fired_at`` — previous fire time, or null on first fire
    """
    return {
        "fired_at": fired_at.isoformat(),
        "scheduled_for": scheduled_for.isoformat(),
        "last_fired_at": (
            previous_last_fired_at.isoformat() if previous_last_fired_at else None
        ),
    }
