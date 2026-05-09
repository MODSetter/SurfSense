"""<workspace_tree> injection (cloud only)."""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from app.agents.new_chat.filesystem_selection import FilesystemMode
from app.agents.new_chat.middleware import KnowledgeTreeMiddleware


def build_knowledge_tree_mw(
    *,
    filesystem_mode: FilesystemMode,
    search_space_id: int,
    llm: BaseChatModel,
) -> KnowledgeTreeMiddleware | None:
    if filesystem_mode != FilesystemMode.CLOUD:
        return None
    return KnowledgeTreeMiddleware(
        search_space_id=search_space_id,
        filesystem_mode=filesystem_mode,
        llm=llm,
    )
