"""Request and response shapes for the podcast API.

Read models surface the lifecycle state the frontend can't derive from Zero (the
deserialized brief and transcript); the action requests carry just what each
guarded transition needs.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.podcasts.duration_limits import (
    DEFAULT_MAX_SECONDS,
    DEFAULT_MIN_SECONDS,
    MAX_DURATION_SECONDS,
    MIN_DURATION_SECONDS,
)
from app.podcasts.persistence import Podcast, PodcastStatus
from app.podcasts.schemas import PodcastSpec, Transcript
from app.podcasts.service import has_stored_episode, read_spec, read_transcript

# Defaults applied when a create request omits brief sizing; the brief gate lets
# the user adjust before any cost is incurred.
DEFAULT_SPEAKER_COUNT = 2


class CreatePodcastRequest(BaseModel):
    """Create a podcast and kick off brief proposal."""

    title: str = Field(..., min_length=1, max_length=500)
    search_space_id: int
    source_content: str = Field(..., min_length=1)
    thread_id: int | None = None
    speaker_count: int = Field(default=DEFAULT_SPEAKER_COUNT, ge=1, le=6)
    min_seconds: int = Field(
        default=DEFAULT_MIN_SECONDS,
        ge=MIN_DURATION_SECONDS,
        le=MAX_DURATION_SECONDS,
    )
    max_seconds: int = Field(
        default=DEFAULT_MAX_SECONDS,
        ge=MIN_DURATION_SECONDS,
        le=MAX_DURATION_SECONDS,
    )
    focus: str | None = Field(default=None, max_length=2000)


class UpdateSpecRequest(BaseModel):
    """Replace the brief at the gate, guarded by the expected version."""

    spec: PodcastSpec
    expected_version: int = Field(..., ge=1)


class VoiceOption(BaseModel):
    """One selectable voice surfaced to the brief editor."""

    voice_id: str
    display_name: str
    language: str
    gender: str


class LanguageOptions(BaseModel):
    """The languages the brief editor may offer for the active provider.

    When ``allows_custom`` is true the list is a curated starting point and
    the editor accepts any BCP-47 tag beyond it.
    """

    languages: list[str]
    allows_custom: bool


class PodcastSummary(BaseModel):
    """Lightweight list item."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    status: PodcastStatus
    created_at: datetime
    search_space_id: int
    thread_id: int | None = None


class PodcastDetail(BaseModel):
    """Full podcast state for the detail view and action responses."""

    id: int
    title: str
    status: PodcastStatus
    spec_version: int
    spec: PodcastSpec | None
    transcript: Transcript | None
    has_audio: bool
    duration_seconds: int | None
    error: str | None
    created_at: datetime
    search_space_id: int
    thread_id: int | None

    @classmethod
    def of(cls, podcast: Podcast) -> PodcastDetail:
        return cls(
            id=podcast.id,
            title=podcast.title,
            status=PodcastStatus(podcast.status),
            spec_version=podcast.spec_version,
            spec=read_spec(podcast),
            transcript=read_transcript(podcast),
            has_audio=has_stored_episode(podcast),
            duration_seconds=podcast.duration_seconds,
            error=podcast.error,
            created_at=podcast.created_at,
            search_space_id=podcast.search_space_id,
            thread_id=podcast.thread_id,
        )
