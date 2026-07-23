"""Audio-rendering task: RENDERING -> READY.

Synthesises and merges the approved transcript, stores the MP3 in the object
store, and marks the podcast ready. The working directory is stable per podcast
so a re-render (e.g. after a voice change) reuses the segment cache.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from sqlalchemy import select

from app.celery_app import celery_app
from app.observability import analytics as ph_analytics
from app.podcasts.persistence import PodcastRepository
from app.podcasts.rendering import PodcastRenderer
from app.podcasts.service import (
    InvalidTransitionError,
    PodcastService,
    read_spec,
    read_transcript,
)
from app.podcasts.storage import purge_audio_object, store_audio
from app.podcasts.tts import get_text_to_speech
from app.podcasts.voices import get_voice_catalog
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task

from .runtime import mark_failed

logger = logging.getLogger(__name__)

_WORKDIR_BASE = Path(tempfile.gettempdir()) / "surfsense_podcasts"


@celery_app.task(name="podcast.render_audio", bind=True)
def render_audio_task(self, podcast_id: int) -> dict:
    try:
        return run_async_celery_task(lambda: _render_audio(podcast_id))
    except Exception as exc:
        logger.error("Podcast %s render failed: %s", podcast_id, exc)
        message = str(exc)
        run_async_celery_task(lambda: mark_failed(podcast_id, message))
        return {"status": "failed", "podcast_id": podcast_id}


async def _render_audio(podcast_id: int) -> dict:
    async with get_celery_session_maker()() as session:
        repo = PodcastRepository(session)
        podcast = await repo.get(podcast_id)
        if podcast is None:
            raise ValueError(f"podcast {podcast_id} not found")

        spec = read_spec(podcast)
        transcript = read_transcript(podcast)
        if spec is None or transcript is None:
            raise ValueError(f"podcast {podcast_id} is missing brief or transcript")

        renderer = PodcastRenderer(
            tts=get_text_to_speech(), catalog=get_voice_catalog()
        )
        workdir = _WORKDIR_BASE / str(podcast_id)
        workdir.mkdir(parents=True, exist_ok=True)
        rendered = await renderer.render(
            spec=spec, transcript=transcript, workdir=workdir
        )

        superseded_key = podcast.storage_key

        backend_name, key = await store_audio(
            workspace_id=podcast.workspace_id,
            podcast_id=podcast_id,
            data=rendered.data,
        )
        try:
            await PodcastService(session).attach_audio(
                podcast, storage_backend=backend_name, storage_key=key
            )
            await session.commit()

            # Credit-consuming deliverable; the frontend never confirms the
            # render finished. Owner (workspace.user_id) resolved lazily so
            # disabled installs pay nothing for the extra query.
            if ph_analytics.is_enabled():
                # Local import: app.db <-> app.podcasts.persistence have a
                # module-init cycle; deferring keeps this task importable.
                from app.db import Workspace

                owner_id = await session.scalar(
                    select(Workspace.user_id).where(
                        Workspace.id == podcast.workspace_id
                    )
                )
                if owner_id:
                    ph_analytics.capture(
                        "podcast_generated",
                        distinct_id=str(owner_id),
                        properties={
                            "workspace_id": podcast.workspace_id,
                            "podcast_id": podcast_id,
                        },
                        groups={"workspace": str(podcast.workspace_id)},
                    )
        except InvalidTransitionError:
            # A user back-out won the race (e.g. the regeneration was
            # reverted): drop the stale render and leave the row alone.
            await purge_audio_object(key)
            return {"status": "superseded", "podcast_id": podcast_id}

    # Purge only after the new audio is committed, so a failed re-render never
    # destroys the episode the user can still play.
    await purge_audio_object(superseded_key)
    return {"status": "ready", "podcast_id": podcast_id}
