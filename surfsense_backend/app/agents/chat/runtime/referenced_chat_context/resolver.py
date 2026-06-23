"""Access-checked fetch of ``@``-mentioned chat threads.

Turns a turn's ``mentioned_thread_ids`` into ``ReferencedChat`` records
the agent can consume as background context. Resolution is fail-closed:
a thread the requester cannot read, or one outside the active search
space, is silently dropped rather than leaked.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import ChatVisibility, NewChatMessage, NewChatMessageRole, NewChatThread
from app.tasks.chat.llm_history_normalizer import (
    assistant_content_to_llm_text,
    user_content_to_llm_content,
)

from .models import ReferencedChat, ReferencedChatTurn

logger = logging.getLogger(__name__)


def _accessible_thread_filter(user_uuid: UUID | None):
    """Visibility predicate mirroring ``new_chat_routes.search_threads``.

    A thread is referenceable when the requester created it or it is
    shared with the search space. Legacy null-creator threads are
    excluded (fail-closed) — referencing them is a rare edge case not
    worth widening the surface for.
    """
    shared = NewChatThread.visibility == ChatVisibility.SEARCH_SPACE
    if user_uuid is None:
        return shared
    return (NewChatThread.created_by_id == user_uuid) | shared


async def resolve_referenced_chats(
    session: AsyncSession,
    *,
    search_space_id: int,
    requesting_user_id: str | None,
    current_chat_id: int,
    mentioned_thread_ids: list[int] | None,
) -> list[ReferencedChat]:
    """Resolve referenced thread IDs into access-checked transcripts.

    Order of the input IDs is preserved. The active thread
    (``current_chat_id``) is dropped so a chat never references itself.
    Threads with no visible turns are omitted so the caller can skip an
    empty context block.
    """
    if not mentioned_thread_ids:
        return []

    user_uuid: UUID | None = None
    if requesting_user_id:
        try:
            user_uuid = UUID(requesting_user_id)
        except (TypeError, ValueError):
            logger.warning(
                "resolve_referenced_chats: invalid user_id=%r; "
                "restricting to shared threads",
                requesting_user_id,
            )

    requested_ids = [
        tid for tid in dict.fromkeys(mentioned_thread_ids) if tid != current_chat_id
    ]
    if not requested_ids:
        return []

    thread_rows = await session.execute(
        select(NewChatThread).where(
            NewChatThread.id.in_(requested_ids),
            NewChatThread.search_space_id == search_space_id,
            _accessible_thread_filter(user_uuid),
        )
    )
    threads_by_id = {row.id: row for row in thread_rows.scalars().all()}
    if not threads_by_id:
        return []

    turns_by_thread = await _load_turns(session, list(threads_by_id.keys()))

    referenced: list[ReferencedChat] = []
    for thread_id in requested_ids:
        thread = threads_by_id.get(thread_id)
        if thread is None:
            logger.debug(
                "resolve_referenced_chats: dropping thread id=%s "
                "(not accessible in space=%s)",
                thread_id,
                search_space_id,
            )
            continue
        turns = turns_by_thread.get(thread_id, [])
        if not turns:
            continue
        referenced.append(
            ReferencedChat(
                thread_id=thread.id,
                title=str(thread.title or "Untitled chat"),
                turns=turns,
            )
        )
    return referenced


async def _load_turns(
    session: AsyncSession,
    thread_ids: list[int],
) -> dict[int, list[ReferencedChatTurn]]:
    """Load visible user/assistant turns for each thread, in order."""
    rows = await session.execute(
        select(NewChatMessage)
        .where(
            NewChatMessage.thread_id.in_(thread_ids),
            NewChatMessage.role.in_(
                [NewChatMessageRole.USER, NewChatMessageRole.ASSISTANT]
            ),
        )
        .order_by(NewChatMessage.thread_id, NewChatMessage.created_at)
    )

    turns_by_thread: dict[int, list[ReferencedChatTurn]] = {}
    for message in rows.scalars().all():
        text = _visible_text(message).strip()
        if not text:
            continue
        turns_by_thread.setdefault(message.thread_id, []).append(
            ReferencedChatTurn(role=message.role.value, text=text)
        )
    return turns_by_thread


def _visible_text(message: NewChatMessage) -> str:
    """Extract only the user-visible text of a persisted message.

    Drops images, reasoning, and tool/UI blocks so the transcript reads
    like the conversation a human would see.
    """
    if message.role == NewChatMessageRole.ASSISTANT:
        return assistant_content_to_llm_text(message.content)
    user_content = user_content_to_llm_content(message.content, allow_images=False)
    return user_content if isinstance(user_content, str) else ""


__all__ = [
    "ReferencedChat",
    "ReferencedChatTurn",
    "resolve_referenced_chats",
]
