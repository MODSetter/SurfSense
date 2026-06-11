"""Internal shapes the transcript graph passes between its nodes.

These are generation-time artifacts (the outline and per-segment drafts), not
persisted or API-facing. Segment drafts reuse :class:`TranscriptTurn` so the
speaker-slot contract and turn validation are identical to the final transcript.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.podcasts.schemas import TranscriptTurn


class OutlineSegment(BaseModel):
    """One planned beat of the conversation, drafted independently."""

    title: str = Field(..., min_length=1)
    talking_points: list[str] = Field(default_factory=list)
    target_words: int = Field(..., ge=1)


class Outline(BaseModel):
    """The full plan: ordered segments sized to the target duration."""

    segments: list[OutlineSegment] = Field(..., min_length=1)


class SegmentDraft(BaseModel):
    """The dialogue a single segment produced."""

    turns: list[TranscriptTurn] = Field(default_factory=list)
