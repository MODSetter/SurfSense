"""Celery tasks for cloning public chats."""

import asyncio
import logging

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.celery_app import celery_app
from app.config import config

logger = logging.getLogger(__name__)


def get_celery_session_maker():
    """Create a new async session maker for Celery tasks."""
    engine = create_async_engine(
        config.DATABASE_URL,
        poolclass=NullPool,
        echo=False,
    )
    return async_sessionmaker(engine, expire_on_commit=False)


@celery_app.task(name="clone_public_chat", bind=True)
def clone_public_chat_task(
    self,
    share_token: str,
    user_id: str,
) -> dict:
    """
    Celery task to clone a public chat to user's account.

    Args:
        share_token: Public share token of the chat to clone
        user_id: UUID string of the user cloning the chat

    Returns:
        dict with status and thread_id on success, or error info on failure
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        result = loop.run_until_complete(_run_clone(share_token, user_id))
        return result
    except Exception as e:
        logger.error(f"Error cloning public chat: {e!s}")
        return {"status": "error", "error": str(e)}
    finally:
        asyncio.set_event_loop(None)
        loop.close()


async def _run_clone(share_token: str, user_id: str) -> dict:
    """Run the clone operation with a fresh database session."""
    from uuid import UUID

    from app.services.public_chat_service import clone_public_chat

    async with get_celery_session_maker()() as session:
        return await clone_public_chat(
            session=session,
            share_token=share_token,
            user_id=UUID(user_id),
        )
