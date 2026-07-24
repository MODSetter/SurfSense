"""Propose a podcast's initial brief spec."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.podcasts.duration_limits import DEFAULT_MAX_SECONDS, DEFAULT_MIN_SECONDS
from app.podcasts.persistence import PodcastRepository
from app.podcasts.schemas import PodcastSpec
from app.podcasts.service import preferences_from

from .config import DEFAULT_SPEAKER_COUNT
from .graph import graph as brief_graph
from .state import BriefState


async def propose_brief(
    session: AsyncSession,
    *,
    workspace_id: int,
    speaker_count: int = DEFAULT_SPEAKER_COUNT,
    min_seconds: int = DEFAULT_MIN_SECONDS,
    max_seconds: int = DEFAULT_MAX_SECONDS,
    focus: str | None = None,
) -> PodcastSpec:
    """Reuse the last-used language and voices, else English; return the spec."""
    last_language, last_voices = preferences_from(
        await PodcastRepository(session).latest_with_spec(workspace_id)
    )
    config = {
        "configurable": {
            "speaker_count": speaker_count,
            "min_seconds": min_seconds,
            "max_seconds": max_seconds,
            "focus": focus,
            "last_used_language": last_language,
            "last_used_voices": last_voices,
        }
    }
    result = await brief_graph.ainvoke(BriefState(), config=config)
    return result["spec"]
