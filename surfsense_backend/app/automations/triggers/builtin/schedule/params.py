"""``ScheduleTriggerParams`` — params for the ``schedule`` trigger type."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .cron import InvalidCronError, validate_cron


class ScheduleTriggerParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cron: str = Field(
        ..., description="Five-field cron expression.", examples=["0 9 * * 1-5"]
    )
    timezone: str = Field(..., description="IANA timezone.", examples=["Africa/Kigali"])

    @model_validator(mode="after")
    def _validate(self) -> ScheduleTriggerParams:
        try:
            validate_cron(self.cron, self.timezone)
        except InvalidCronError as exc:
            raise ValueError(str(exc)) from exc
        return self
