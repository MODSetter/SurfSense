"""Brief-proposal task: PENDING -> AWAITING_BRIEF.

Runs the (cheap, token-light) brief graph to detect language and propose a spec,
seeded with the user's last-used language/voice preferences. Pushes the result
straight onto the row so the frontend sees the brief gate open via Zero.
"""

from __future__ import annotations

import logging

from app.celery_app import celery_app
from app.podcasts.generation.brief.graph import graph as brief_graph
from app.podcasts.generation.brief.state import BriefState
from app.podcasts.persistence import PodcastRepository
from app.podcasts.service import PodcastService, preferences_from
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task

from .runtime import mark_failed

logger = logging.getLogger(__name__)


@celery_app.task(name="podcast.propose_brief", bind=True)
def propose_brief_task(self, podcast_id: int, search_space_id: int) -> dict:
    try:
        return run_async_celery_task(
            lambda: _propose_brief(podcast_id, search_space_id)
        )
    except Exception as exc:  # noqa: BLE001 - record and report, never crash worker
        logger.error("Podcast %s brief proposal failed: %s", podcast_id, exc)
        run_async_celery_task(lambda: mark_failed(podcast_id, str(exc)))
        return {"status": "failed", "podcast_id": podcast_id}


async def _propose_brief(podcast_id: int, search_space_id: int) -> dict:
    async with get_celery_session_maker()() as session:
        repo = PodcastRepository(session)
        podcast = await repo.get(podcast_id)
        if podcast is None:
            raise ValueError(f"podcast {podcast_id} not found")

        last_language, last_voices = preferences_from(
            await repo.latest_with_spec(search_space_id)
        )
        state = BriefState(
            db_session=session, source_content=podcast.source_content or ""
        )
        config = {
            "configurable": {
                "search_space_id": search_space_id,
                "last_used_language": last_language,
                "last_used_voices": last_voices,
            }
        }
        result = await brief_graph.ainvoke(state, config=config)

        await PodcastService(session).attach_brief(podcast, result["spec"])
        await session.commit()
        return {"status": "awaiting_brief", "podcast_id": podcast_id}
