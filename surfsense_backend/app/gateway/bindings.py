"""External chat binding helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    ChatVisibility,
    ExternalChatBindingState,
    ExternalChatBinding,
    NewChatThread,
)


async def get_or_create_thread_for_binding(
    session: AsyncSession,
    binding: ExternalChatBinding,
) -> NewChatThread:
    if binding.new_chat_thread_id is not None:
        result = await session.execute(
            select(NewChatThread).where(NewChatThread.id == binding.new_chat_thread_id)
        )
        thread = result.scalars().first()
        if thread is not None and not thread.archived:
            return thread

    thread = NewChatThread(
        title="Telegram chat",
        search_space_id=binding.search_space_id,
        created_by_id=binding.user_id,
        visibility=ChatVisibility.PRIVATE,
        source="telegram",
        external_chat_binding_id=binding.id,
    )
    session.add(thread)
    await session.flush()
    binding.new_chat_thread_id = thread.id
    return thread


def suspend_binding(binding: ExternalChatBinding, reason: str) -> None:
    now = datetime.now(UTC)
    binding.state = ExternalChatBindingState.SUSPENDED
    binding.suspended_at = now
    binding.suspended_reason = reason


def revoke_binding(binding: ExternalChatBinding) -> None:
    now = datetime.now(UTC)
    binding.state = ExternalChatBindingState.REVOKED
    binding.revoked_at = now
    binding.new_chat_thread_id = None


def resume_binding(binding: ExternalChatBinding) -> None:
    binding.state = ExternalChatBindingState.BOUND
    binding.suspended_at = None
    binding.suspended_reason = None

