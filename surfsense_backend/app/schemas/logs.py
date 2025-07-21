from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict
from .base import IDModel, TimestampModel
from app.db import LogLevel, LogStatus

class LogBase(BaseModel):
    level: LogLevel
    status: LogStatus
    message: str
    source: Optional[str] = None
    log_metadata: Optional[Dict[str, Any]] = None

class LogCreate(BaseModel):
    level: LogLevel
    status: LogStatus
    message: str
    source: Optional[str] = None
    log_metadata: Optional[Dict[str, Any]] = None
    search_space_id: int

class LogUpdate(BaseModel):
    level: Optional[LogLevel] = None
    status: Optional[LogStatus] = None
    message: Optional[str] = None
    source: Optional[str] = None
    log_metadata: Optional[Dict[str, Any]] = None

class LogRead(LogBase, IDModel, TimestampModel):
    id: int
    created_at: datetime
    search_space_id: int

    model_config = ConfigDict(from_attributes=True)

class LogFilter(BaseModel):
    level: Optional[LogLevel] = None
    status: Optional[LogStatus] = None
    source: Optional[str] = None
    search_space_id: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True) 