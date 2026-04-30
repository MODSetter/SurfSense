"""Dependency dict for :func:`app.agents.new_chat.tools.registry.build_tools` in multi-agent graphs."""

from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import ChatVisibility


def build_registry_dependencies(
    *,
    db_session: AsyncSession,
    search_space_id: int,
    user_id: str,
    thread_id: str,
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
        "thread_id": thread_id,
        "llm": llm,
        "firecrawl_api_key": firecrawl_api_key,
        "connector_service": connector_service,
        "available_connectors": available_connectors,
        "available_document_types": available_document_types,
        "thread_visibility": thread_visibility,
    }
