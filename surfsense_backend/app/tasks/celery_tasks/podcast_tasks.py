"""Celery tasks for podcast generation."""

import asyncio
import logging
import sys

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.celery_app import celery_app
from app.config import config
from app.tasks.podcast_tasks import generate_chat_podcast

# Import for content-based podcast (new-chat)
from app.agents.podcaster.graph import graph as podcaster_graph
from app.agents.podcaster.state import State as PodcasterState
from app.db import Podcast

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


@celery_app.task(name="generate_chat_podcast", bind=True)
def generate_chat_podcast_task(
    self,
    chat_id: int,
    search_space_id: int,
    user_id: int,
    podcast_title: str | None = None,
    user_prompt: str | None = None,
):
    """
    Celery task to generate podcast from chat.

    Args:
        chat_id: ID of the chat to generate podcast from
        search_space_id: ID of the search space
        user_id: ID of the user,
        podcast_title: Title for the podcast
        user_prompt: Optional prompt from the user to guide the podcast generation
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(
            _generate_chat_podcast(
                chat_id, search_space_id, user_id, podcast_title, user_prompt
            )
        )
        loop.run_until_complete(loop.shutdown_asyncgens())
    finally:
        asyncio.set_event_loop(None)
        loop.close()


async def _generate_chat_podcast(
    chat_id: int,
    search_space_id: int,
    user_id: int,
    podcast_title: str | None = None,
    user_prompt: str | None = None,
):
    """Generate chat podcast with new session."""
    async with get_celery_session_maker()() as session:
        try:
            await generate_chat_podcast(
                session, chat_id, search_space_id, user_id, podcast_title, user_prompt
            )
        except Exception as e:
            logger.error(f"Error generating podcast from chat: {e!s}")
            raise


# =============================================================================
# Content-based podcast generation (for new-chat)
# =============================================================================


def _clear_active_podcast_redis_key(search_space_id: int) -> None:
    """Clear the active podcast task key from Redis when task completes."""
    import os

    import redis

    try:
        redis_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
        client = redis.from_url(redis_url, decode_responses=True)
        key = f"podcast:active:{search_space_id}"
        client.delete(key)
        logger.info(f"Cleared active podcast key for search_space_id={search_space_id}")
    except Exception as e:
        logger.warning(f"Could not clear active podcast key: {e}")


@celery_app.task(name="generate_content_podcast", bind=True)
def generate_content_podcast_task(
    self,
    source_content: str,
    search_space_id: int,
    user_id: str,
    podcast_title: str = "SurfSense Podcast",
    user_prompt: str | None = None,
) -> dict:
    """
    Celery task to generate podcast from source content (for new-chat).

    Unlike generate_chat_podcast which requires a chat_id, this task
    generates a podcast directly from provided content.

    Args:
        source_content: The text content to convert into a podcast
        search_space_id: ID of the search space
        user_id: ID of the user (as string)
        podcast_title: Title for the podcast
        user_prompt: Optional instructions for podcast style/tone

    Returns:
        dict with podcast_id on success, or error info on failure
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        result = loop.run_until_complete(
            _generate_content_podcast(
                source_content,
                search_space_id,
                user_id,
                podcast_title,
                user_prompt,
            )
        )
        loop.run_until_complete(loop.shutdown_asyncgens())
        return result
    except Exception as e:
        logger.error(f"Error generating content podcast: {e!s}")
        return {"status": "error", "error": str(e)}
    finally:
        # Always clear the active podcast key when task completes (success or failure)
        _clear_active_podcast_redis_key(search_space_id)
        asyncio.set_event_loop(None)
        loop.close()


async def _generate_content_podcast(
    source_content: str,
    search_space_id: int,
    user_id: str,
    podcast_title: str = "SurfSense Podcast",
    user_prompt: str | None = None,
) -> dict:
    """Generate content-based podcast with new session."""
    async with get_celery_session_maker()() as session:
        try:
            # Configure the podcaster graph
            graph_config = {
                "configurable": {
                    "podcast_title": podcast_title,
                    "user_id": str(user_id),
                    "search_space_id": search_space_id,
                    "user_prompt": user_prompt,
                }
            }

            # Initialize the podcaster state with the source content
            initial_state = PodcasterState(
                source_content=source_content,
                db_session=session,
            )

            # Run the podcaster graph
            result = await podcaster_graph.ainvoke(initial_state, config=graph_config)

            # Extract results
            podcast_transcript = result.get("podcast_transcript", [])
            file_path = result.get("final_podcast_file_path", "")

            # Convert transcript to serializable format
            serializable_transcript = []
            for entry in podcast_transcript:
                if hasattr(entry, "speaker_id"):
                    serializable_transcript.append({
                        "speaker_id": entry.speaker_id,
                        "dialog": entry.dialog
                    })
                else:
                    serializable_transcript.append({
                        "speaker_id": entry.get("speaker_id", 0),
                        "dialog": entry.get("dialog", "")
                    })

            # Save podcast to database
            podcast = Podcast(
                title=podcast_title,
                podcast_transcript=serializable_transcript,
                file_location=file_path,
                search_space_id=search_space_id,
                chat_id=None,  # No chat_id for new-chat podcasts
                chat_state_version=None,
            )
            session.add(podcast)
            await session.commit()
            await session.refresh(podcast)

            logger.info(f"Successfully generated content podcast: {podcast.id}")

            return {
                "status": "success",
                "podcast_id": podcast.id,
                "title": podcast_title,
                "transcript_entries": len(serializable_transcript),
            }

        except Exception as e:
            logger.error(f"Error in _generate_content_podcast: {e!s}")
            await session.rollback()
            raise
