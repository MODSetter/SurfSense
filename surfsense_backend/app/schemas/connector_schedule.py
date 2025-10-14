from datetime import datetime, time
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.db import ScheduleType

from .base import IDModel, TimestampModel


class ConnectorScheduleBase(BaseModel):
    connector_id: int
    search_space_id: int
    schedule_type: ScheduleType
    cron_expression: str | None = None
    is_active: bool = True
    
    # Enhanced time selection options
    daily_time: Optional[time] = None  # For DAILY schedules (default: 02:00)
    weekly_day: Optional[int] = None  # For WEEKLY schedules (0=Monday, 6=Sunday, default: 6)
    weekly_time: Optional[time] = None  # For WEEKLY schedules (default: 02:00)
    hourly_minute: Optional[int] = None  # For HOURLY schedules (0-59, default: 0)

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
    
    @field_validator("daily_time")
    @classmethod
    def validate_daily_time(cls, v: time | None, values: dict) -> time | None:
        """Validate daily_time is only provided for DAILY schedule type."""
        schedule_type = values.data.get("schedule_type")
        if v is not None and schedule_type != ScheduleType.DAILY:
            raise ValueError(
                "daily_time should only be provided for DAILY schedule_type"
            )
        return v
    
    @field_validator("weekly_day")
    @classmethod
    def validate_weekly_day(cls, v: int | None, values: dict) -> int | None:
        """Validate weekly_day is only provided for WEEKLY schedule type."""
        schedule_type = values.data.get("schedule_type")
        if v is not None and schedule_type != ScheduleType.WEEKLY:
            raise ValueError(
                "weekly_day should only be provided for WEEKLY schedule_type"
            )
        if v is not None and not (0 <= v <= 6):
            raise ValueError("weekly_day must be between 0 (Monday) and 6 (Sunday)")
        return v
    
    @field_validator("weekly_time")
    @classmethod
    def validate_weekly_time(cls, v: time | None, values: dict) -> time | None:
        """Validate weekly_time is only provided for WEEKLY schedule type."""
        schedule_type = values.data.get("schedule_type")
        if v is not None and schedule_type != ScheduleType.WEEKLY:
            raise ValueError(
                "weekly_time should only be provided for WEEKLY schedule_type"
            )
        return v
    
    @field_validator("hourly_minute")
    @classmethod
    def validate_hourly_minute(cls, v: int | None, values: dict) -> int | None:
        """Validate hourly_minute is only provided for HOURLY schedule type."""
        schedule_type = values.data.get("schedule_type")
        if v is not None and schedule_type != ScheduleType.HOURLY:
            raise ValueError(
                "hourly_minute should only be provided for HOURLY schedule_type"
            )
        if v is not None and not (0 <= v <= 59):
            raise ValueError("hourly_minute must be between 0 and 59")
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

