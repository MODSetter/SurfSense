"""Access-checked lookup of chat threads the requester may read.

The single place chat visibility is enforced: a thread is readable when it is
shared with the search space, the requester created it, or it is a legacy
null-creator thread and the requester owns the search space. Anything else is
dropped (fail-closed).
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import ChatVisibility, NewChatThread, SearchSpace

logger = logging.getLogger(__name__)


def _visibility_predicate(user_uuid: UUID | None, *, include_legacy: bool):
    """SQL predicate for threads the requester may read."""
    conditions = [NewChatThread.visibility == ChatVisibility.SEARCH_SPACE]
    if user_uuid is not None:
        conditions.append(NewChatThread.created_by_id == user_uuid)
    if include_legacy:
        conditions.append(NewChatThread.created_by_id.is_(None))
    return or_(*conditions)


async def accessible_threads(
    session: AsyncSession,
    *,
    search_space_id: int,
    requesting_user_id: str | None,
    thread_ids: list[int],
    exclude_thread_id: int | None = None,
) -> list[NewChatThread]:
    """Threads in this space the requester may read, in requested order.

    Input order is preserved and de-duplicated; ``exclude_thread_id`` (the
    active chat) is removed so a chat never references itself. Inaccessible or
    foreign ids are silently dropped.
    """
    requested = [tid for tid in dict.fromkeys(thread_ids) if tid != exclude_thread_id]
    if not requested:
        return []

    user_uuid: UUID | None = None
    if requesting_user_id:
        try:
            user_uuid = UUID(requesting_user_id)
        except (TypeError, ValueError):
            logger.warning(
                "accessible_threads: invalid user_id=%r; restricting to shared",
                requesting_user_id,
            )

    # Legacy null-creator threads are readable only by the search-space owner.
    include_legacy = False
    if user_uuid is not None:
        owner_id = await session.scalar(
            select(SearchSpace.user_id).where(SearchSpace.id == search_space_id)
        )
        include_legacy = owner_id == user_uuid

    rows = await session.execute(
        select(NewChatThread).where(
            NewChatThread.id.in_(requested),
            NewChatThread.search_space_id == search_space_id,
            _visibility_predicate(user_uuid, include_legacy=include_legacy),
        )
    )
    threads_by_id = {row.id: row for row in rows.scalars().all()}
    return [threads_by_id[tid] for tid in requested if tid in threads_by_id]


__all__ = ["accessible_threads"]
