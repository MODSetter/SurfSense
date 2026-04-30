"""Dependency dict for :func:`app.agents.new_chat.tools.registry.build_tools` on expert subgraphs."""

from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import ChatVisibility


def coerce_thread_id_for_registry(thread_id: str | int | None) -> int | None:
    """Normalize chat thread id for registry tools that FK to ``new_chat_threads.id``.

    ``create_surfsense_deep_agent`` passes an ``int``; multi-agent wiring may pass
    ``str(chat_id)`` for LangGraph/checkpointer consistency. AsyncPG requires ``int``
    for integer columns.
    """
    if thread_id is None:
        return None
    if isinstance(thread_id, int):
        return thread_id
    s = str(thread_id).strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    return None


def build_registry_dependencies(
    *,
    db_session: AsyncSession,
    search_space_id: int,
    user_id: str,
    thread_id: str | int | None,
    llm: BaseChatModel | None = None,
    firecrawl_api_key: str | None = None,
    connector_service: Any | None = None,
    available_connectors: list[str] | None = None,
    available_document_types: list[str] | None = None,
    thread_visibility: ChatVisibility = ChatVisibility.PRIVATE,
) -> dict[str, Any]:
    """Union of kwargs commonly required by registry factories across category slices.

    Individual categories enable a subset of tools; each tool still validates its own
    ``ToolDefinition.requires`` against this dict.
    """
    return {
        "db_session": db_session,
        "search_space_id": search_space_id,
        "user_id": user_id,
        "thread_id": coerce_thread_id_for_registry(thread_id),
        "llm": llm,
        "firecrawl_api_key": firecrawl_api_key,
        "connector_service": connector_service,
        "available_connectors": available_connectors,
        "available_document_types": available_document_types,
        "thread_visibility": thread_visibility,
    }
