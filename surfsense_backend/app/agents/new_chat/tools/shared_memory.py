"""Shared (team) memory backend for search-space-scoped AI context."""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import MemoryCategory, SharedMemory, User

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


def _to_uuid(value: str | UUID) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(value)


async def save_shared_memory(
    db_session: AsyncSession,
    search_space_id: int,
    created_by_id: str | UUID,
    content: str,
    category: str = "fact",
) -> dict[str, Any]:
    category = category.lower() if category else "fact"
    valid = ["preference", "fact", "instruction", "context"]
    if category not in valid:
        category = "fact"
    try:
        count = await get_shared_memory_count(db_session, search_space_id)
        if count >= MAX_MEMORIES_PER_SEARCH_SPACE:
            await delete_oldest_shared_memory(db_session, search_space_id)
        embedding = config.embedding_model_instance.embed(content)
        row = SharedMemory(
            search_space_id=search_space_id,
            created_by_id=_to_uuid(created_by_id),
            memory_text=content,
            category=MemoryCategory(category),
            embedding=embedding,
        )
        db_session.add(row)
        await db_session.commit()
        await db_session.refresh(row)
        return {
            "status": "saved",
            "memory_id": row.id,
            "memory_text": content,
            "category": category,
            "message": f"I'll remember: {content}",
        }
    except Exception as e:
        logger.exception("Failed to save shared memory: %s", e)
        await db_session.rollback()
        return {
            "status": "error",
            "error": str(e),
            "message": "Failed to save memory. Please try again.",
        }


async def recall_shared_memory(
    db_session: AsyncSession,
    search_space_id: int,
    query: str | None = None,
    category: str | None = None,
    top_k: int = DEFAULT_RECALL_TOP_K,
) -> dict[str, Any]:
    top_k = min(max(top_k, 1), 20)
    try:
        valid_categories = ["preference", "fact", "instruction", "context"]
        stmt = select(SharedMemory).where(
            SharedMemory.search_space_id == search_space_id
        )
        if category and category in valid_categories:
            stmt = stmt.where(SharedMemory.category == MemoryCategory(category))
        if query:
            query_embedding = config.embedding_model_instance.embed(query)
            stmt = stmt.order_by(
                SharedMemory.embedding.op("<=>")(query_embedding)
            ).limit(top_k)
        else:
            stmt = stmt.order_by(SharedMemory.updated_at.desc()).limit(top_k)
        result = await db_session.execute(stmt)
        rows = result.scalars().all()
        memory_list = [
            {
                "id": m.id,
                "memory_text": m.memory_text,
                "category": m.category.value if m.category else "unknown",
                "updated_at": m.updated_at.isoformat() if m.updated_at else None,
                "created_by_id": str(m.created_by_id) if m.created_by_id else None,
            }
            for m in rows
        ]
        created_by_ids = list({m["created_by_id"] for m in memory_list if m["created_by_id"]})
        created_by_map: dict[str, str] = {}
        if created_by_ids:
            uuids = [UUID(uid) for uid in created_by_ids]
            users_result = await db_session.execute(
                select(User).where(User.id.in_(uuids))
            )
            for u in users_result.scalars().all():
                created_by_map[str(u.id)] = u.display_name or "A team member"
        formatted_context = format_shared_memories_for_context(
            memory_list, created_by_map
        )
        return {
            "status": "success",
            "count": len(memory_list),
            "memories": memory_list,
            "formatted_context": formatted_context,
        }
    except Exception as e:
        logger.exception("Failed to recall shared memory: %s", e)
        await db_session.rollback()
        return {
            "status": "error",
            "error": str(e),
            "memories": [],
            "formatted_context": "Failed to recall memories.",
        }


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
