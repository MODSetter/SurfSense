"""Commit staged cloud filesystem mutations to Postgres at end of turn."""

from __future__ import annotations

from app.agents.new_chat.filesystem_selection import FilesystemMode
from app.agents.new_chat.middleware import KnowledgeBasePersistenceMiddleware


def build_kb_persistence_mw(
    *,
    filesystem_mode: FilesystemMode,
    search_space_id: int,
    user_id: str | None,
    thread_id: int | None,
) -> KnowledgeBasePersistenceMiddleware | None:
    if filesystem_mode != FilesystemMode.CLOUD:
        return None
    return KnowledgeBasePersistenceMiddleware(
        search_space_id=search_space_id,
        created_by_id=user_id,
        filesystem_mode=filesystem_mode,
        thread_id=thread_id,
    )
