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
    transcript_entries: int | None = None

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_with_entries(cls, obj):
        """Create PodcastRead with transcript_entries computed."""
        data = {
            "id": obj.id,
            "title": obj.title,
            "podcast_transcript": obj.podcast_transcript,
            "file_location": obj.file_location,
            "search_space_id": obj.search_space_id,
            "status": obj.status,
            "created_at": obj.created_at,
            "transcript_entries": len(obj.podcast_transcript)
            if obj.podcast_transcript
            else None,
        }
        return cls(**data)
