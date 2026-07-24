"""Resolve ``@chat`` mentions into pointer references.

Chats are not KB-indexed, so a chat reference is a pointer only; its turns are
read on demand via the chat read tool, not injected here. Only the title is
needed, so this takes the cheap access-checked path and never loads transcripts.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import ChatReference
from .access import accessible_threads


async def resolve_chat_references(
    session: AsyncSession,
    *,
    workspace_id: int,
    requesting_user_id: str | None,
    current_chat_id: int,
    thread_ids: list[int],
) -> list[ChatReference]:
    """Map ``@chat`` thread ids to access-checked pointers (titles only)."""
    if not thread_ids:
        return []

    threads = await accessible_threads(
        session,
        workspace_id=workspace_id,
        requesting_user_id=requesting_user_id,
        thread_ids=thread_ids,
        exclude_thread_id=current_chat_id,
    )
    return [
        ChatReference(entity_id=thread.id, label=str(thread.title or "Untitled chat"))
        for thread in threads
    ]


__all__ = ["resolve_chat_references"]
