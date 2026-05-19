"""Background memory extraction for the SurfSense agent."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.db import User, shielded_async_session
from app.services.memory import MemoryScope, extract_and_save

logger = logging.getLogger(__name__)


async def extract_and_save_memory(
    *,
    user_message: str,
    user_id: str | None,
    llm: Any,
) -> None:
    """Fire-and-forget personal memory extraction.

    The service uses structured output, so free-form ``NO_UPDATE`` text can no
    longer be accidentally persisted as memory.
    """
    if not user_id:
        return

    try:
        uid = UUID(user_id) if isinstance(user_id, str) else user_id
        async with shielded_async_session() as session:
            user = await session.get(User, uid)
            actor_display_name = user.display_name if user else None
            result = await extract_and_save(
                scope=MemoryScope.USER,
                target_id=uid,
                user_message=user_message,
                actor_display_name=actor_display_name,
                session=session,
                llm=llm,
            )
            logger.info(
                "Background memory extraction for user %s: %s",
                uid,
                result.status,
            )
    except Exception:
        logger.exception("Background user memory extraction failed")


async def extract_and_save_team_memory(
    *,
    user_message: str,
    search_space_id: int | None,
    llm: Any,
    author_display_name: str | None = None,
) -> None:
    """Fire-and-forget team-level memory extraction."""
    if not search_space_id:
        return

    try:
        async with shielded_async_session() as session:
            result = await extract_and_save(
                scope=MemoryScope.TEAM,
                target_id=search_space_id,
                user_message=user_message,
                actor_display_name=author_display_name,
                session=session,
                llm=llm,
            )
            logger.info(
                "Background team memory extraction for space %s: %s",
                search_space_id,
                result.status,
            )
    except Exception:
        logger.exception("Background team memory extraction failed")
