"""KB priority planner: <priority_documents> injection."""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from app.agents.chat.multi_agent_chat.shared.filesystem_selection import FilesystemMode
from app.agents.chat.multi_agent_chat.shared.middleware.knowledge_search import (
    KnowledgePriorityMiddleware,
)
from app.services.llm_service import get_planner_llm


def build_knowledge_priority_mw(
    *,
    llm: BaseChatModel,
    search_space_id: int,
    filesystem_mode: FilesystemMode,
    available_connectors: list[str] | None,
    available_document_types: list[str] | None,
    mentioned_document_ids: list[int] | None,
    preinjection_enabled: bool = True,
) -> KnowledgePriorityMiddleware:
    """Build the KB priority middleware.

    When ``preinjection_enabled`` is False (the lazy default), the middleware
    runs in mentions-only mode: it skips the expensive planner LLM + embedding
    + hybrid search and only surfaces explicit @-mentions. The main agent is
    expected to pull relevant KB content on demand via the
    ``search_knowledge_base`` tool instead.
    """
    return KnowledgePriorityMiddleware(
        llm=llm,
        planner_llm=get_planner_llm(),
        search_space_id=search_space_id,
        filesystem_mode=filesystem_mode,
        available_connectors=available_connectors,
        available_document_types=available_document_types,
        mentioned_document_ids=mentioned_document_ids,
        inject_system_message=False,
        mentions_only=not preinjection_enabled,
    )
