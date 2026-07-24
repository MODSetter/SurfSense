"""<workspace_tree> injection (cloud only)."""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from app.agents.chat.multi_agent_chat.shared.filesystem_selection import FilesystemMode

from .middleware import KnowledgeTreeMiddleware


def build_knowledge_tree_mw(
    *,
    filesystem_mode: FilesystemMode,
    workspace_id: int,
    llm: BaseChatModel,
) -> KnowledgeTreeMiddleware | None:
    if filesystem_mode != FilesystemMode.CLOUD:
        return None
    return KnowledgeTreeMiddleware(
        workspace_id=workspace_id,
        filesystem_mode=filesystem_mode,
        llm=llm,
        inject_system_message=False,
    )
