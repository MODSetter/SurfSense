"""Shared (team) memory backend for search-space-scoped AI context."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SharedMemory

logger = logging.getLogger(__name__)

DEFAULT_RECALL_TOP_K = 5
MAX_MEMORIES_PER_SEARCH_SPACE = 250


async def get_shared_memory_count(
    db_session: AsyncSession,
    search_space_id: int,
) -> int:
    result = await db_session.execute(
        select(SharedMemory).where(SharedMemory.search_space_id == search_space_id)
    )
    return len(result.scalars().all())


async def delete_oldest_shared_memory(
    db_session: AsyncSession,
    search_space_id: int,
) -> None:
    result = await db_session.execute(
        select(SharedMemory)
        .where(SharedMemory.search_space_id == search_space_id)
        .order_by(SharedMemory.updated_at.asc())
        .limit(1)
    )
    oldest = result.scalars().first()
    if oldest:
        await db_session.delete(oldest)
        await db_session.commit()
