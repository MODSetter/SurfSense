"""Podcast schemas for API responses."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel


class PodcastStatusEnum(str, Enum):
    PENDING = "pending"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


class PodcastBase(BaseModel):
    """Base podcast schema."""

    title: str
    podcast_transcript: list[dict[str, Any]] | None = None
    file_location: str | None = None
    search_space_id: int


class PodcastCreate(PodcastBase):
    """Schema for creating a podcast."""

    pass


class PodcastUpdate(BaseModel):
    """Schema for updating a podcast."""

    title: str | None = None
    podcast_transcript: list[dict[str, Any]] | None = None
    file_location: str | None = None


class PodcastRead(PodcastBase):
    """Schema for reading a podcast."""

    id: int
    status: PodcastStatusEnum = PodcastStatusEnum.READY
    created_at: datetime

    class Config:
        from_attributes = True
