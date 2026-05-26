"""``ScheduleTriggerConfig`` — config for the ``schedule`` trigger type."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ScheduleTriggerConfig(BaseModel):
    """Config for a cron-driven trigger.

    Validated against ``AutomationTrigger.config`` whenever the
    persisted ``type`` is ``schedule``. The cron expression is
    evaluated by Celery Beat's source; the timezone is an IANA name
    (e.g., ``Africa/Kigali``) and is required so the user's cron is
    unambiguous across DST boundaries.
    """

    model_config = ConfigDict(extra="forbid")

    cron: str = Field(
        ...,
        description=(
            "Five-field cron expression. Minimum resolution is one "
            "minute; the form editor warns when intervals tighter "
            "than 15 minutes are used."
        ),
        examples=["0 9 * * 1-5"],
    )
    timezone: str = Field(
        ...,
        description="IANA timezone name (e.g., 'Africa/Kigali', 'UTC').",
        examples=["Africa/Kigali"],
    )
