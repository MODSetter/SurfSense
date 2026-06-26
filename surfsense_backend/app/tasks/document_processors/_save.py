"""Unified document save/update logic for file processors."""

import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, DocumentStatus, DocumentType
from app.utils.document_converters import (
    create_document_chunks,
    embed_text,
    generate_content_hash,
)

from ._helpers import (
    find_existing_document_with_migration,
    get_google_drive_unique_identifier,
    handle_existing_document_update,
)
from .base import get_current_timestamp, safe_set_chunks

# ---------------------------------------------------------------------------
# Unified save function
# ---------------------------------------------------------------------------


async def save_file_document(
    session: AsyncSession,
    file_name: str,
    markdown_content: str,
    workspace_id: int,
    user_id: str,
    etl_service: str,
    connector: dict | None = None,
) -> Document | None:
    """
    Process and store a file document with deduplication and migration support.

    Handles both creating new documents and updating existing ones.  This is
    the single implementation behind the per-ETL-service wrapper functions.

    Args:
        session: Database session
        file_name: Name of the processed file
        markdown_content: Markdown content to store
        workspace_id: ID of the workspace
        user_id: ID of the user
        etl_service: Name of the ETL service (UNSTRUCTURED, LLAMACLOUD, DOCLING)
        connector: Optional connector info for Google Drive files

    Returns:
        Document object if successful, None if duplicate detected
    """
    try:
        primary_hash, legacy_hash = get_google_drive_unique_identifier(
            connector, file_name, workspace_id
        )
        content_hash = generate_content_hash(markdown_content, workspace_id)

        existing_document = await find_existing_document_with_migration(
            session, primary_hash, legacy_hash, content_hash
        )

        if existing_document:
            should_skip, doc = await handle_existing_document_update(
                session,
                existing_document,
                content_hash,
                connector,
                file_name,
                primary_hash,
            )
            if should_skip:
                return doc

        document_content = f"File: {file_name}\n\n{markdown_content[:4000]}"
        document_embedding = embed_text(document_content)
        chunks = await create_document_chunks(markdown_content)
        doc_metadata = {"FILE_NAME": file_name, "ETL_SERVICE": etl_service}

        if existing_document:
            existing_document.title = file_name
            existing_document.content = document_content
            existing_document.content_hash = content_hash
            existing_document.embedding = document_embedding
            existing_document.document_metadata = doc_metadata
            await safe_set_chunks(session, existing_document, chunks)
            existing_document.source_markdown = markdown_content
            existing_document.content_needs_reindexing = False
            existing_document.updated_at = get_current_timestamp()
            existing_document.status = DocumentStatus.ready()

            await session.commit()
            await session.refresh(existing_document)
            return existing_document

        doc_type = DocumentType.FILE
        if connector and connector.get("type") == DocumentType.GOOGLE_DRIVE_FILE:
            doc_type = DocumentType.GOOGLE_DRIVE_FILE

        document = Document(
            workspace_id=workspace_id,
            title=file_name,
            document_type=doc_type,
            document_metadata=doc_metadata,
            content=document_content,
            embedding=document_embedding,
            chunks=chunks,
            content_hash=content_hash,
            unique_identifier_hash=primary_hash,
            source_markdown=markdown_content,
            content_needs_reindexing=False,
            updated_at=get_current_timestamp(),
            created_by_id=user_id,
            connector_id=connector.get("connector_id") if connector else None,
            status=DocumentStatus.ready(),
        )
        session.add(document)
        await session.commit()
        await session.refresh(document)
        return document

    except SQLAlchemyError as db_error:
        await session.rollback()
        if "ix_documents_content_hash" in str(db_error):
            logging.warning(
                "content_hash collision during commit for %s (%s). Skipping.",
                file_name,
                etl_service,
            )
            return None
        raise db_error
    except Exception as e:
        await session.rollback()
        raise RuntimeError(
            f"Failed to process file document using {etl_service}: {e!s}"
        ) from e
