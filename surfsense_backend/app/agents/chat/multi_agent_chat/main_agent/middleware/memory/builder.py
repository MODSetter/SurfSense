"""User/team memory injection prepended to the conversation."""

from __future__ import annotations

from app.db import ChatVisibility

from .middleware import MemoryInjectionMiddleware


def build_memory_mw(
    *,
    user_id: str | None,
    workspace_id: int,
    visibility: ChatVisibility,
) -> MemoryInjectionMiddleware:
    return MemoryInjectionMiddleware(
        user_id=user_id,
        workspace_id=workspace_id,
        thread_visibility=visibility,
    )
