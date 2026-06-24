"""Resolved ``@``-references and their pointer block.

References are scope, not content: they tell the model what the user pointed
at this turn so it can retrieve from those sources with tools.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.runtime.path_resolver import build_path_index
from app.schemas.new_chat import MentionedDocumentInfo

from .chat import resolve_chat_references
from .connectors import resolve_connector_references
from .documents import resolve_document_references
from .folders import resolve_folder_references
from .models import (
    ChatReference,
    ConnectorReference,
    DocumentReference,
    FolderReference,
    Reference,
    ReferenceKind,
)
from .reference_pointers import render_reference_pointers


async def resolve_references(
    session: AsyncSession,
    *,
    search_space_id: int,
    requesting_user_id: str | None,
    current_chat_id: int,
    document_ids: list[int] | None = None,
    folder_ids: list[int] | None = None,
    connector_ids: list[int] | None = None,
    connector_chips: list[MentionedDocumentInfo] | None = None,
    thread_ids: list[int] | None = None,
) -> list[Reference]:
    """Resolve a turn's ``@``-references into one ordered pointer list.

    Order is documents, folders, connectors, chats. The path index is built
    once and shared by the document and folder resolvers.
    """
    references: list[Reference] = []

    if document_ids or folder_ids:
        index = await build_path_index(session, search_space_id)
        if document_ids:
            references += await resolve_document_references(
                session,
                search_space_id=search_space_id,
                document_ids=document_ids,
                index=index,
            )
        if folder_ids:
            references += await resolve_folder_references(
                session,
                search_space_id=search_space_id,
                folder_ids=folder_ids,
                index=index,
            )

    if connector_ids:
        references += await resolve_connector_references(
            session,
            search_space_id=search_space_id,
            connector_ids=connector_ids,
            chips=connector_chips,
        )

    if thread_ids:
        references += await resolve_chat_references(
            session,
            search_space_id=search_space_id,
            requesting_user_id=requesting_user_id,
            current_chat_id=current_chat_id,
            thread_ids=thread_ids,
        )

    return references


__all__ = [
    "ChatReference",
    "ConnectorReference",
    "DocumentReference",
    "FolderReference",
    "Reference",
    "ReferenceKind",
    "render_reference_pointers",
    "resolve_references",
]
