"""Podcast schemas for API responses."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


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
    created_at: datetime

    class Config:
        from_attributes = True
