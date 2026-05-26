"""``ScheduleTriggerConfig`` — config for the ``schedule`` trigger type."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ScheduleTriggerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cron: str = Field(..., description="Five-field cron expression.", examples=["0 9 * * 1-5"])
    timezone: str = Field(..., description="IANA timezone.", examples=["Africa/Kigali"])
