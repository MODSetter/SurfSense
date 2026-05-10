"""User/team memory injection prepended to the conversation."""

from __future__ import annotations

from app.agents.new_chat.middleware import MemoryInjectionMiddleware
from app.db import ChatVisibility


def build_memory_mw(
    *,
    user_id: str | None,
    search_space_id: int,
    visibility: ChatVisibility,
) -> MemoryInjectionMiddleware:
    return MemoryInjectionMiddleware(
        user_id=user_id,
        search_space_id=search_space_id,
        thread_visibility=visibility,
    )
