"""Report schemas for API responses."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ReportBase(BaseModel):
    """Base report schema."""

    title: str
    content: str | None = None
    report_style: str | None = None
    search_space_id: int


class ReportRead(BaseModel):
    """Schema for reading a report (list view, no content)."""

    id: int
    title: str
    report_style: str | None = None
    report_metadata: dict[str, Any] | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class ReportContentRead(BaseModel):
    """Schema for reading a report with full Markdown content."""

    id: int
    title: str
    content: str | None = None
    report_metadata: dict[str, Any] | None = None

    class Config:
        from_attributes = True

