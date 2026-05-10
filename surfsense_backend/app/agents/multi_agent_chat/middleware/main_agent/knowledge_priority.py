"""KB priority planner: <priority_documents> injection."""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from app.agents.new_chat.filesystem_selection import FilesystemMode
from app.agents.new_chat.middleware import KnowledgePriorityMiddleware


def build_knowledge_priority_mw(
    *,
    llm: BaseChatModel,
    search_space_id: int,
    filesystem_mode: FilesystemMode,
    available_connectors: list[str] | None,
    available_document_types: list[str] | None,
    mentioned_document_ids: list[int] | None,
) -> KnowledgePriorityMiddleware:
    return KnowledgePriorityMiddleware(
        llm=llm,
        search_space_id=search_space_id,
        filesystem_mode=filesystem_mode,
        available_connectors=available_connectors,
        available_document_types=available_document_types,
        mentioned_document_ids=mentioned_document_ids,
    )
