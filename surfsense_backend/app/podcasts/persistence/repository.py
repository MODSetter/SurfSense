"""Data access for the ``podcasts`` table.

A thin async repository so the service and tasks never write raw queries. It
only loads and persists rows; lifecycle rules and (de)serialization live in the
service.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Podcast


class PodcastRepository:
    """Loads and stores :class:`Podcast` rows for one session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, podcast_id: int) -> Podcast | None:
        return await self._session.get(Podcast, podcast_id)

    async def add(self, podcast: Podcast) -> Podcast:
        """Persist a new row and assign its primary key."""
        self._session.add(podcast)
        await self._session.flush()
        return podcast

    async def latest_with_spec(self, workspace_id: int) -> Podcast | None:
        """Most recent podcast in the space that has a stored brief.

        Used to seed language/voice defaults for a new podcast from what the
        user chose last.
        """
        result = await self._session.execute(
            select(Podcast)
            .where(
                Podcast.workspace_id == workspace_id,
                Podcast.spec.is_not(None),
            )
            .order_by(Podcast.created_at.desc())
            .limit(1)
        )
        return result.scalars().first()
