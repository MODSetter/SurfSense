"""Schedule trigger source: Celery Beat ticks the selector every minute.

``BEAT_SCHEDULE`` is merged into ``celery_app.conf.beat_schedule``. Per-row cron
math is precomputed (the ``next_fire_at`` column), so each tick is an indexed
lookup rather than N cron evaluations.
"""

from __future__ import annotations

from celery.schedules import crontab

TASK_NAME = "automation_schedule_select"

BEAT_SCHEDULE = {
    "automation-schedule-select": {
        "task": TASK_NAME,
        "schedule": crontab(minute="*"),
        "options": {"expires": 50},
    },
}
