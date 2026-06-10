"""Mutable state threaded through the brief-planning graph."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.podcasts.schemas import PodcastSpec


@dataclass
class BriefState:
    """Runtime inputs and the proposed spec the graph produces."""

    db_session: AsyncSession
    source_content: str
    detected_language: str | None = None
    spec: PodcastSpec | None = None
