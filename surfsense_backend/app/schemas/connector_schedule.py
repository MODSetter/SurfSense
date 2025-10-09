from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.db import ScheduleType

from .base import IDModel, TimestampModel


class ConnectorScheduleBase(BaseModel):
    connector_id: int
    search_space_id: int
    schedule_type: ScheduleType
    cron_expression: str | None = None
    is_active: bool = True

    @field_validator("cron_expression")
    @classmethod
    def validate_cron_expression(cls, v: str | None, values: dict) -> str | None:
        """Validate cron expression is provided when schedule_type is CUSTOM."""
        schedule_type = values.data.get("schedule_type")
        if schedule_type == ScheduleType.CUSTOM and not v:
            raise ValueError(
                "cron_expression is required when schedule_type is CUSTOM"
            )
        if schedule_type != ScheduleType.CUSTOM and v:
            raise ValueError(
                f"cron_expression should only be provided for CUSTOM schedule_type, got {schedule_type}"
            )
        return v


class ConnectorScheduleCreate(ConnectorScheduleBase):
    """Schema for creating a new connector schedule."""

    pass


class ConnectorScheduleUpdate(BaseModel):
    """Schema for updating an existing connector schedule."""

    schedule_type: ScheduleType | None = None
    cron_expression: str | None = None
    is_active: bool | None = None

    @field_validator("cron_expression")
    @classmethod
    def validate_cron_expression_update(cls, v: str | None, values: dict) -> str | None:
        """Validate cron expression for updates."""
        schedule_type = values.data.get("schedule_type")
        if schedule_type == ScheduleType.CUSTOM and v is None:
            raise ValueError(
                "cron_expression is required when schedule_type is CUSTOM"
            )
        return v


class ConnectorScheduleRead(ConnectorScheduleBase, IDModel, TimestampModel):
    """Schema for reading a connector schedule."""

    last_run_at: datetime | None = None
    next_run_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

