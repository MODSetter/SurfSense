"""
Service layer for chat session state (live collaboration).
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import ChatSessionState


async def get_session_state(
    session: AsyncSession,
    thread_id: int,
) -> ChatSessionState | None:
    """Get the current session state for a thread."""
    result = await session.execute(
        select(ChatSessionState)
        .options(selectinload(ChatSessionState.ai_responding_to_user))
        .filter(ChatSessionState.thread_id == thread_id)
    )
    return result.scalar_one_or_none()


async def set_ai_responding(
    session: AsyncSession,
    thread_id: int,
    user_id: UUID,
) -> ChatSessionState:
    """Mark AI as responding to a specific user. Uses upsert for atomicity."""
    now = datetime.now(UTC)
    upsert_query = insert(ChatSessionState).values(
        thread_id=thread_id,
        ai_responding_to_user_id=user_id,
        updated_at=now,
    )
    upsert_query = upsert_query.on_conflict_do_update(
        index_elements=["thread_id"],
        set_={
            "ai_responding_to_user_id": user_id,
            "updated_at": now,
        },
    )
    await session.execute(upsert_query)
    await session.commit()

    return await get_session_state(session, thread_id)


async def clear_ai_responding(
    session: AsyncSession,
    thread_id: int,
) -> ChatSessionState | None:
    """Clear AI responding state when response is complete."""
    state = await get_session_state(session, thread_id)
    if state:
        state.ai_responding_to_user_id = None
        state.updated_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(state)
    return state
