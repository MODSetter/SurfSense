"""Resolve ``@chat`` mentions into pointer references.

Chats are not KB-indexed, so a chat reference is a pointer only; its turns are
read on demand via the chat read tool, not injected here. Access checking is
delegated to the authoritative referenced-chat resolver so the rules live in one
place.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.runtime.referenced_chat_context.resolver import (
    resolve_referenced_chats,
)

from .models import ChatReference


async def resolve_chat_references(
    session: AsyncSession,
    *,
    search_space_id: int,
    requesting_user_id: str | None,
    current_chat_id: int,
    thread_ids: list[int],
) -> list[ChatReference]:
    """Map ``@chat`` thread ids to access-checked pointers (titles only)."""
    if not thread_ids:
        return []

    chats = await resolve_referenced_chats(
        session,
        search_space_id=search_space_id,
        requesting_user_id=requesting_user_id,
        current_chat_id=current_chat_id,
        mentioned_thread_ids=thread_ids,
    )
    return [
        ChatReference(entity_id=chat.thread_id, label=chat.title) for chat in chats
    ]


__all__ = ["resolve_chat_references"]
