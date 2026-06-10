"""Mutable state threaded through the transcript-drafting graph."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.podcasts.schemas import Transcript, TranscriptTurn

from .planning import Outline


@dataclass
class TranscriptState:
    """Source content plus the intermediate and final drafting artifacts."""

    db_session: AsyncSession
    source_content: str
    outline: Outline | None = None
    drafted_turns: list[TranscriptTurn] = field(default_factory=list)
    transcript: Transcript | None = None
