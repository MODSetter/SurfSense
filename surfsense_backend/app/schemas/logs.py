from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.db import LogLevel, LogStatus

from .base import IDModel, TimestampModel


class LogBase(BaseModel):
    level: LogLevel
    status: LogStatus
    message: str
    source: str | None = None
    log_metadata: dict[str, Any] | None = None


class LogCreate(BaseModel):
    level: LogLevel
    status: LogStatus
    message: str
    source: str | None = None
    log_metadata: dict[str, Any] | None = None
    search_space_id: int


class LogUpdate(BaseModel):
    level: LogLevel | None = None
    status: LogStatus | None = None
    message: str | None = None
    source: str | None = None
    log_metadata: dict[str, Any] | None = None


class LogRead(LogBase, IDModel, TimestampModel):
    id: int
    created_at: datetime
    search_space_id: int

    model_config = ConfigDict(from_attributes=True)


class LogFilter(BaseModel):
    level: LogLevel | None = None
    status: LogStatus | None = None
    source: str | None = None
    search_space_id: int | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
