"""Shared (team) memory backend for search-space-scoped AI context."""

import logging
from typing import Any

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


def format_shared_memories_for_context(
    memories: list[dict[str, Any]],
    created_by_map: dict[str, str] | None = None,
) -> str:
    if not memories:
        return "No relevant team memories found."
    created_by_map = created_by_map or {}
    parts = ["<team_memories>"]
    for memory in memories:
        category = memory.get("category", "unknown")
        text = memory.get("memory_text", "")
        updated = memory.get("updated_at", "")
        created_by_id = memory.get("created_by_id")
        added_by = (
            created_by_map.get(str(created_by_id), "A team member")
            if created_by_id is not None
            else "A team member"
        )
        parts.append(
            f"  <memory category='{category}' updated='{updated}' added_by='{added_by}'>{text}</memory>"
        )
    parts.append("</team_memories>")
    return "\n".join(parts)
