"""Celery tasks for podcast generation."""

import asyncio
import logging
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.agents.podcaster.graph import graph as podcaster_graph
from app.agents.podcaster.state import State as PodcasterState
from app.celery_app import celery_app
from app.config import config
from app.db import Podcast, PodcastStatus

logger = logging.getLogger(__name__)

if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except AttributeError:
        logger.warning(
            "WindowsProactorEventLoopPolicy is unavailable; async subprocess support may fail."
        )


def get_celery_session_maker():
    """
    Create a new async session maker for Celery tasks.
    This is necessary because Celery tasks run in a new event loop,
    and the default session maker is bound to the main app's event loop.
    """
    engine = create_async_engine(
        config.DATABASE_URL,
        poolclass=NullPool,  # Don't use connection pooling for Celery tasks
        echo=False,
    )
    return async_sessionmaker(engine, expire_on_commit=False)


# =============================================================================
# Content-based podcast generation (for new-chat)
# =============================================================================


def _clear_generating_podcast(search_space_id: int) -> None:
    """Clear the generating podcast marker from Redis when task completes."""
    import os

    import redis

    try:
        redis_url = os.getenv(
            "REDIS_APP_URL",
            os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
        )
        client = redis.from_url(redis_url, decode_responses=True)
        key = f"podcast:generating:{search_space_id}"
        client.delete(key)
        logger.info(
            f"Cleared generating podcast key for search_space_id={search_space_id}"
        )
    except Exception as e:
        logger.warning(f"Could not clear generating podcast key: {e}")


@celery_app.task(name="generate_content_podcast", bind=True)
def generate_content_podcast_task(
    self,
    podcast_id: int,
    source_content: str,
    search_space_id: int,
    user_prompt: str | None = None,
) -> dict:
    """
    Celery task to generate podcast from source content.
    Updates existing podcast record created by the tool.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        result = loop.run_until_complete(
            _generate_content_podcast(
                podcast_id,
                source_content,
                search_space_id,
                user_prompt,
            )
        )
        loop.run_until_complete(loop.shutdown_asyncgens())
        return result
    except Exception as e:
        logger.error(f"Error generating content podcast: {e!s}")
        loop.run_until_complete(_mark_podcast_failed(podcast_id))
        return {"status": "failed", "podcast_id": podcast_id}
    finally:
        _clear_generating_podcast(search_space_id)
        asyncio.set_event_loop(None)
        loop.close()


async def _mark_podcast_failed(podcast_id: int) -> None:
    """Mark a podcast as failed in the database."""
    async with get_celery_session_maker()() as session:
        try:
            result = await session.execute(
                select(Podcast).filter(Podcast.id == podcast_id)
            )
            podcast = result.scalars().first()
            if podcast:
                podcast.status = PodcastStatus.FAILED
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to mark podcast as failed: {e}")


async def _generate_content_podcast(
    podcast_id: int,
    source_content: str,
    search_space_id: int,
    user_prompt: str | None = None,
) -> dict:
    """Generate content-based podcast and update existing record."""
    async with get_celery_session_maker()() as session:
        result = await session.execute(select(Podcast).filter(Podcast.id == podcast_id))
        podcast = result.scalars().first()

        if not podcast:
            raise ValueError(f"Podcast {podcast_id} not found")

        try:
            podcast.status = PodcastStatus.GENERATING
            await session.commit()

            graph_config = {
                "configurable": {
                    "podcast_title": podcast.title,
                    "search_space_id": search_space_id,
                    "user_prompt": user_prompt,
                }
            }

            initial_state = PodcasterState(
                source_content=source_content,
                db_session=session,
            )

            graph_result = await podcaster_graph.ainvoke(
                initial_state, config=graph_config
            )

            podcast_transcript = graph_result.get("podcast_transcript", [])
            file_path = graph_result.get("final_podcast_file_path", "")

            serializable_transcript = []
            for entry in podcast_transcript:
                if hasattr(entry, "speaker_id"):
                    serializable_transcript.append(
                        {"speaker_id": entry.speaker_id, "dialog": entry.dialog}
                    )
                else:
                    serializable_transcript.append(
                        {
                            "speaker_id": entry.get("speaker_id", 0),
                            "dialog": entry.get("dialog", ""),
                        }
                    )

            podcast.podcast_transcript = serializable_transcript
            podcast.file_location = file_path
            podcast.status = PodcastStatus.READY
            await session.commit()

            logger.info(f"Successfully generated podcast: {podcast.id}")

            return {
                "status": "ready",
                "podcast_id": podcast.id,
                "title": podcast.title,
                "transcript_entries": len(serializable_transcript),
            }

        except Exception as e:
            logger.error(f"Error in _generate_content_podcast: {e!s}")
            podcast.status = PodcastStatus.FAILED
            await session.commit()
            raise
