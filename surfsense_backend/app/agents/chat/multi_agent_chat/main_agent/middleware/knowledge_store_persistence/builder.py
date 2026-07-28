"""Build the git-native persistence middleware when the flag selects it."""

from __future__ import annotations

from typing import Any

from app.agents.chat.multi_agent_chat.shared.filesystem_selection import FilesystemMode
from app.knowledge_store.settings import load_knowledge_store_settings

from .middleware import KnowledgeStorePersistenceMiddleware


def build_knowledge_store_persistence_mw(
    *,
    filesystem_mode: FilesystemMode,
    workspace_id: int,
    user_id: str | None,
    thread_id: int | None,
    llm: Any,
) -> KnowledgeStorePersistenceMiddleware | None:
    if filesystem_mode != FilesystemMode.CLOUD:
        return None
    if not load_knowledge_store_settings().enabled:
        return None
    return KnowledgeStorePersistenceMiddleware(
        workspace_id=workspace_id,
        created_by_id=user_id,
        thread_id=thread_id,
        llm=llm,
    )
