"""Celery tasks for podcast generation."""

import asyncio
import logging
import sys

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.celery_app import celery_app
from app.config import config
from app.tasks.podcast_tasks import generate_chat_podcast

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
    self, chat_id: int, search_space_id: int, podcast_title: str, user_id: int
):
    """
    Celery task to generate podcast from chat.

    Args:
        chat_id: ID of the chat to generate podcast from
        search_space_id: ID of the search space
        podcast_title: Title for the podcast
        user_id: ID of the user
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(
            _generate_chat_podcast(chat_id, search_space_id, podcast_title, user_id)
        )
        loop.run_until_complete(loop.shutdown_asyncgens())
    finally:
        asyncio.set_event_loop(None)
        loop.close()


async def _generate_chat_podcast(
    chat_id: int, search_space_id: int, podcast_title: str, user_id: int
):
    """Generate chat podcast with new session."""
    async with get_celery_session_maker()() as session:
        try:
            await generate_chat_podcast(
                session, chat_id, search_space_id, podcast_title, user_id
            )
        except Exception as e:
            logger.error(f"Error generating podcast from chat: {e!s}")
            raise
