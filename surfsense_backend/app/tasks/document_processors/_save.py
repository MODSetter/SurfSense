"""
Unified document save/update logic for file processors.

Replaces the three nearly-identical ``add_received_file_document_using_*``
functions with a single ``save_file_document`` function plus thin wrappers
for backward compatibility.
"""

import logging

from langchain_core.documents import Document as LangChainDocument
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, DocumentStatus, DocumentType
from app.services.llm_service import get_user_long_context_llm
from app.utils.document_converters import (
    create_document_chunks,
    embed_text,
    generate_content_hash,
    generate_document_summary,
)

from ._helpers import (
    find_existing_document_with_migration,
    get_google_drive_unique_identifier,
    handle_existing_document_update,
)
from .base import get_current_timestamp, safe_set_chunks

# ---------------------------------------------------------------------------
# Summary generation
# ---------------------------------------------------------------------------


async def _generate_summary(
    markdown_content: str,
    file_name: str,
    etl_service: str,
    user_llm,
    enable_summary: bool,
) -> tuple[str, list[float]]:
    """
    Generate a document summary and embedding.

    Docling uses its own large-document summary strategy; other ETL services
    use the standard ``generate_document_summary`` helper.
    """
    if not enable_summary:
        summary = f"File: {file_name}\n\n{markdown_content[:4000]}"
        return summary, embed_text(summary)

    if etl_service == "DOCLING":
        from app.services.docling_service import create_docling_service

        docling_service = create_docling_service()
        summary_text = await docling_service.process_large_document_summary(
            content=markdown_content, llm=user_llm, document_title=file_name
        )

        meta = {
            "file_name": file_name,
            "etl_service": etl_service,
            "document_type": "File Document",
        }
        parts = ["# DOCUMENT METADATA"]
        for key, value in meta.items():
            if value:
                formatted_key = key.replace("_", " ").title()
                parts.append(f"**{formatted_key}:** {value}")

        enhanced = "\n".join(parts) + "\n\n# DOCUMENT SUMMARY\n\n" + summary_text
        return enhanced, embed_text(enhanced)

    # Standard summary (Unstructured / LlamaCloud / others)
    meta = {
        "file_name": file_name,
        "etl_service": etl_service,
        "document_type": "File Document",
    }
    return await generate_document_summary(markdown_content, user_llm, meta)


# ---------------------------------------------------------------------------
# Unified save function
# ---------------------------------------------------------------------------


async def save_file_document(
    session: AsyncSession,
    file_name: str,
    markdown_content: str,
    search_space_id: int,
    user_id: str,
    etl_service: str,
    connector: dict | None = None,
    enable_summary: bool = True,
) -> Document | None:
    """
    Process and store a file document with deduplication and migration support.

    Handles both creating new documents and updating existing ones.  This is
    the single implementation behind the per-ETL-service wrapper functions.

    Args:
        session: Database session
        file_name: Name of the processed file
        markdown_content: Markdown content to store
        search_space_id: ID of the search space
        user_id: ID of the user
        etl_service: Name of the ETL service (UNSTRUCTURED, LLAMACLOUD, DOCLING)
        connector: Optional connector info for Google Drive files
        enable_summary: Whether to generate an AI summary

    Returns:
        Document object if successful, None if duplicate detected
    """
    try:
        primary_hash, legacy_hash = get_google_drive_unique_identifier(
            connector, file_name, search_space_id
        )
        content_hash = generate_content_hash(markdown_content, search_space_id)

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

        user_llm = await get_user_long_context_llm(session, user_id, search_space_id)
        if not user_llm:
            raise RuntimeError(
                f"No long context LLM configured for user {user_id} "
                f"in search space {search_space_id}"
            )

        summary_content, summary_embedding = await _generate_summary(
            markdown_content, file_name, etl_service, user_llm, enable_summary
        )
        chunks = await create_document_chunks(markdown_content)
        doc_metadata = {"FILE_NAME": file_name, "ETL_SERVICE": etl_service}

        if existing_document:
            existing_document.title = file_name
            existing_document.content = summary_content
            existing_document.content_hash = content_hash
            existing_document.embedding = summary_embedding
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
            search_space_id=search_space_id,
            title=file_name,
            document_type=doc_type,
            document_metadata=doc_metadata,
            content=summary_content,
            embedding=summary_embedding,
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


# ---------------------------------------------------------------------------
# Backward-compatible wrapper functions
# ---------------------------------------------------------------------------


async def add_received_file_document_using_unstructured(
    session: AsyncSession,
    file_name: str,
    unstructured_processed_elements: list[LangChainDocument],
    search_space_id: int,
    user_id: str,
    connector: dict | None = None,
    enable_summary: bool = True,
) -> Document | None:
    """Process and store a file document using the Unstructured service."""
    from app.utils.document_converters import convert_document_to_markdown

    markdown_content = await convert_document_to_markdown(
        unstructured_processed_elements
    )
    return await save_file_document(
        session,
        file_name,
        markdown_content,
        search_space_id,
        user_id,
        "UNSTRUCTURED",
        connector,
        enable_summary,
    )


async def add_received_file_document_using_llamacloud(
    session: AsyncSession,
    file_name: str,
    llamacloud_markdown_document: str,
    search_space_id: int,
    user_id: str,
    connector: dict | None = None,
    enable_summary: bool = True,
) -> Document | None:
    """Process and store document content parsed by LlamaCloud."""
    return await save_file_document(
        session,
        file_name,
        llamacloud_markdown_document,
        search_space_id,
        user_id,
        "LLAMACLOUD",
        connector,
        enable_summary,
    )


async def add_received_file_document_using_docling(
    session: AsyncSession,
    file_name: str,
    docling_markdown_document: str,
    search_space_id: int,
    user_id: str,
    connector: dict | None = None,
    enable_summary: bool = True,
) -> Document | None:
    """Process and store document content parsed by Docling."""
    return await save_file_document(
        session,
        file_name,
        docling_markdown_document,
        search_space_id,
        user_id,
        "DOCLING",
        connector,
        enable_summary,
    )
