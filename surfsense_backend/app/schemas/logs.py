from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.db import LogLevel, LogStatus

from .base import IDModel, TimestampModel

# Skip reason constants for bulk operations
SKIP_REASON_NOT_ELIGIBLE_RETRY = "Log not eligible for retry"
SKIP_REASON_COULD_NOT_DISMISS = "Log could not be dismissed"


class LogBase(BaseModel):
    level: LogLevel
    status: LogStatus
    message: str
    source: str | None = None
    log_metadata: dict[str, Any] | None = None
    retry_count: int = 0


class LogCreate(BaseModel):
    level: LogLevel
    status: LogStatus
    message: str
    source: str | None = None
    log_metadata: dict[str, Any] | None = None
    search_space_id: int
    retry_count: int = 0


class LogUpdate(BaseModel):
    level: LogLevel | None = None
    status: LogStatus | None = None
    message: str | None = None
    source: str | None = None
    log_metadata: dict[str, Any] | None = None
    retry_count: int | None = None


class LogRead(LogBase, IDModel, TimestampModel):
    id: int
    created_at: datetime
    search_space_id: int
    retry_count: int

    model_config = ConfigDict(from_attributes=True)


class LogFilter(BaseModel):
    level: LogLevel | None = None
    status: LogStatus | None = None
    source: str | None = None
    search_space_id: int | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# Bulk operation response models
class SkippedLog(BaseModel):
    """Model for a skipped log in bulk operations."""
    id: int
    reason: str

    model_config = ConfigDict(from_attributes=True)


class BulkRetryResponse(BaseModel):
    """Response model for bulk retry operation."""
    retried: list[int]
    skipped: list[SkippedLog]
    total: int

    model_config = ConfigDict(from_attributes=True)


class BulkDismissResponse(BaseModel):
    """Response model for bulk dismiss operation."""
    dismissed: list[int]
    skipped: list[SkippedLog]
    total: int

    model_config = ConfigDict(from_attributes=True)
