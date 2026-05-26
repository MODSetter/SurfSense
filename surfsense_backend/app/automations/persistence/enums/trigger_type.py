"""``TriggerType`` — the trigger-kind discriminator (v1 = schedule, manual)."""

from __future__ import annotations

from enum import StrEnum


class TriggerType(StrEnum):
    """Kind of trigger an ``AutomationTrigger`` row represents.

    v1 ships two kinds:

    ``schedule`` — fires on a cron expression managed by Celery Beat.
    ``manual``   — fires on demand from the UI's "Run now" affordance.

    ``webhook`` and ``event`` are deferred to Phase 2 and Phase 3
    respectively; adding them is an enum-value extension only.
    """

    SCHEDULE = "schedule"
    MANUAL = "manual"
