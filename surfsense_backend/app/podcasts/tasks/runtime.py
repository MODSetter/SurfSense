"""Shared plumbing for the podcast Celery tasks.

Each task runs its async body via :func:`run_async_celery_task` and, on any
failure, records the reason on the row through the lifecycle service. Marking
failed is best-effort: a podcast that already reached a terminal state is left
untouched rather than forced.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from app.podcasts.persistence import PodcastRepository
from app.podcasts.service import PodcastError, PodcastService
from app.tasks.celery_tasks import get_celery_session_maker

logger = logging.getLogger(__name__)


@asynccontextmanager
async def billable_session():
    """Session factory for ``billable_call`` inside the worker loop."""
    async with get_celery_session_maker()() as session:
        yield session


async def mark_failed(podcast_id: int, error: str) -> None:
    """Best-effort: move a non-terminal podcast to FAILED with ``error``."""
    async with get_celery_session_maker()() as session:
        repo = PodcastRepository(session)
        podcast = await repo.get(podcast_id)
        if podcast is None:
            return
        try:
            await PodcastService(session).fail(podcast, error)
            await session.commit()
        except PodcastError:
            # Already terminal (e.g. cancelled): nothing to record.
            logger.info("Podcast %s already terminal; not marking failed", podcast_id)
