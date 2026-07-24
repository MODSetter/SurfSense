"""Commit staged cloud filesystem mutations to Postgres at end of turn."""

from __future__ import annotations

from app.agents.chat.multi_agent_chat.shared.filesystem_selection import FilesystemMode

from .middleware import (
    KnowledgeBasePersistenceMiddleware,
)


def build_kb_persistence_mw(
    *,
    filesystem_mode: FilesystemMode,
    workspace_id: int,
    user_id: str | None,
    thread_id: int | None,
) -> KnowledgeBasePersistenceMiddleware | None:
    if filesystem_mode != FilesystemMode.CLOUD:
        return None
    return KnowledgeBasePersistenceMiddleware(
        workspace_id=workspace_id,
        created_by_id=user_id,
        filesystem_mode=filesystem_mode,
        thread_id=thread_id,
    )
