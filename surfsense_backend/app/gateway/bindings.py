"""Gateway binding helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    ChatVisibility,
    GatewayBindingState,
    GatewayConversationBinding,
    NewChatThread,
)


async def get_or_create_thread_for_binding(
    session: AsyncSession,
    binding: GatewayConversationBinding,
) -> NewChatThread:
    if binding.active_thread_id is not None:
        result = await session.execute(
            select(NewChatThread).where(NewChatThread.id == binding.active_thread_id)
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
        binding_id=binding.id,
    )
    session.add(thread)
    await session.flush()
    binding.active_thread_id = thread.id
    return thread


def suspend_binding(binding: GatewayConversationBinding, reason: str) -> None:
    now = datetime.now(UTC)
    binding.state = GatewayBindingState.SUSPENDED
    binding.suspended_at = now
    binding.suspended_reason = reason


def revoke_binding(binding: GatewayConversationBinding) -> None:
    now = datetime.now(UTC)
    binding.state = GatewayBindingState.REVOKED
    binding.revoked_at = now
    binding.active_thread_id = None


def resume_binding(binding: GatewayConversationBinding) -> None:
    binding.state = GatewayBindingState.BOUND
    binding.suspended_at = None
    binding.suspended_reason = None

