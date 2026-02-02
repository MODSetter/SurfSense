"""
Markdown file document processor.
"""

import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, DocumentType
from app.services.llm_service import get_user_long_context_llm
from app.services.task_logging_service import TaskLoggingService
from app.utils.document_converters import (
    create_document_chunks,
    generate_content_hash,
    generate_document_summary,
    generate_unique_identifier_hash,
)

from .base import (
    check_document_by_unique_identifier,
    check_duplicate_document,
    get_current_timestamp,
)


def _get_google_drive_unique_identifier(
    connector: dict | None,
    filename: str,
    search_space_id: int,
) -> tuple[str, str | None]:
    """
    Get unique identifier hash for a file, with special handling for Google Drive.

    For Google Drive files, uses file_id as the unique identifier (doesn't change on rename).
    For other files, uses filename.

    Args:
        connector: Optional connector info dict with type and metadata
        filename: The filename (used for non-Google Drive files or as fallback)
        search_space_id: The search space ID

    Returns:
        Tuple of (primary_hash, legacy_hash or None)
    """
    if connector and connector.get("type") == DocumentType.GOOGLE_DRIVE_FILE:
        metadata = connector.get("metadata", {})
        file_id = metadata.get("google_drive_file_id")

        if file_id:
            primary_hash = generate_unique_identifier_hash(
                DocumentType.GOOGLE_DRIVE_FILE, file_id, search_space_id
            )
            legacy_hash = generate_unique_identifier_hash(
                DocumentType.GOOGLE_DRIVE_FILE, filename, search_space_id
            )
            return primary_hash, legacy_hash

    primary_hash = generate_unique_identifier_hash(
        DocumentType.FILE, filename, search_space_id
    )
    return primary_hash, None


async def _find_existing_document_with_migration(
    session: AsyncSession,
    primary_hash: str,
    legacy_hash: str | None,
    content_hash: str | None = None,
) -> Document | None:
    """
    Find existing document, checking both new hash and legacy hash for migration,
    with fallback to content_hash for cross-source deduplication.
    """
    existing_document = await check_document_by_unique_identifier(session, primary_hash)

    if not existing_document and legacy_hash:
        existing_document = await check_document_by_unique_identifier(
            session, legacy_hash
        )
        if existing_document:
            logging.info(
                "Found legacy document (filename-based hash), will migrate to file_id-based hash"
            )

    # Fallback: check by content_hash to catch duplicates from different sources
    if not existing_document and content_hash:
        existing_document = await check_duplicate_document(session, content_hash)
        if existing_document:
            logging.info(
                f"Found duplicate content from different source (content_hash match). "
                f"Original document ID: {existing_document.id}, type: {existing_document.document_type}"
            )

    return existing_document


async def _handle_existing_document_update(
    session: AsyncSession,
    existing_document: Document,
    content_hash: str,
    connector: dict | None,
    filename: str,
    primary_hash: str,
    task_logger: TaskLoggingService,
    log_entry,
) -> tuple[bool, Document | None]:
    """
    Handle update logic for an existing document.

    Returns:
        Tuple of (should_skip_processing, document_to_return)
    """
    # Check if this document needs hash migration
    if existing_document.unique_identifier_hash != primary_hash:
        existing_document.unique_identifier_hash = primary_hash
        logging.info(f"Migrated document to file_id-based identifier: {filename}")

    # Check if content has changed
    if existing_document.content_hash == content_hash:
        # Content unchanged - check if we need to update metadata (e.g., filename changed)
        if connector and connector.get("type") == DocumentType.GOOGLE_DRIVE_FILE:
            connector_metadata = connector.get("metadata", {})
            new_name = connector_metadata.get("google_drive_file_name")
            # Check both possible keys for old name (FILE_NAME is used in stored documents)
            doc_metadata = existing_document.document_metadata or {}
            old_name = (
                doc_metadata.get("FILE_NAME")
                or doc_metadata.get("google_drive_file_name")
                or doc_metadata.get("file_name")
            )

            if new_name and old_name and old_name != new_name:
                # File was renamed - update title and metadata, skip expensive processing
                from sqlalchemy.orm.attributes import flag_modified

                existing_document.title = new_name
                if not existing_document.document_metadata:
                    existing_document.document_metadata = {}
                existing_document.document_metadata["FILE_NAME"] = new_name
                existing_document.document_metadata["file_name"] = new_name
                existing_document.document_metadata["google_drive_file_name"] = new_name
                flag_modified(existing_document, "document_metadata")
                await session.commit()
                logging.info(
                    f"File renamed in Google Drive: '{old_name}' → '{new_name}' (no re-processing needed)"
                )

        await task_logger.log_task_success(
            log_entry,
            f"Markdown file document unchanged: {filename}",
            {
                "duplicate_detected": True,
                "existing_document_id": existing_document.id,
            },
        )
        logging.info(f"Document for markdown file {filename} unchanged. Skipping.")
        return True, existing_document
    else:
        logging.info(
            f"Content changed for markdown file {filename}. Updating document."
        )
        return False, None


async def add_received_markdown_file_document(
    session: AsyncSession,
    file_name: str,
    file_in_markdown: str,
    search_space_id: int,
    user_id: str,
    connector: dict | None = None,
) -> Document | None:
    """
    Process and store a markdown file document.

    Args:
        session: Database session
        file_name: Name of the markdown file
        file_in_markdown: Content of the markdown file
        search_space_id: ID of the search space
        user_id: ID of the user
        connector: Optional connector info for Google Drive files

    Returns:
        Document object if successful, None if failed
    """
    task_logger = TaskLoggingService(session, search_space_id)

    # Log task start
    log_entry = await task_logger.log_task_start(
        task_name="markdown_file_document",
        source="background_task",
        message=f"Processing markdown file: {file_name}",
        metadata={
            "filename": file_name,
            "user_id": str(user_id),
            "content_length": len(file_in_markdown),
        },
    )

    try:
        # Generate unique identifier hash (uses file_id for Google Drive, filename for others)
        primary_hash, legacy_hash = _get_google_drive_unique_identifier(
            connector, file_name, search_space_id
        )

        # Generate content hash
        content_hash = generate_content_hash(file_in_markdown, search_space_id)

        # Check if document exists (with migration support for Google Drive and content_hash fallback)
        existing_document = await _find_existing_document_with_migration(
            session, primary_hash, legacy_hash, content_hash
        )

        if existing_document:
            # Handle existing document (rename detection, content change check)
            should_skip, doc = await _handle_existing_document_update(
                session,
                existing_document,
                content_hash,
                connector,
                file_name,
                primary_hash,
                task_logger,
                log_entry,
            )
            if should_skip:
                return doc
            # Content changed - continue to update

        # Get user's long context LLM (needed for both create and update)
        user_llm = await get_user_long_context_llm(session, user_id, search_space_id)
        if not user_llm:
            raise RuntimeError(
                f"No long context LLM configured for user {user_id} in search space {search_space_id}"
            )

        # Generate summary with metadata
        document_metadata = {
            "file_name": file_name,
            "document_type": "Markdown File Document",
        }
        summary_content, summary_embedding = await generate_document_summary(
            file_in_markdown, user_llm, document_metadata
        )

        # Process chunks
        chunks = await create_document_chunks(file_in_markdown)

        from app.utils.blocknote_converter import convert_markdown_to_blocknote

        # Convert to BlockNote JSON
        blocknote_json = await convert_markdown_to_blocknote(file_in_markdown)
        if not blocknote_json:
            logging.warning(
                f"Failed to convert {file_name} to BlockNote JSON, document will not be editable"
            )

        # Update or create document
        if existing_document:
            # Update existing document
            existing_document.title = file_name
            existing_document.content = summary_content
            existing_document.content_hash = content_hash
            existing_document.embedding = summary_embedding
            existing_document.document_metadata = {
                "FILE_NAME": file_name,
            }
            existing_document.chunks = chunks
            existing_document.blocknote_document = blocknote_json
            existing_document.updated_at = get_current_timestamp()

            await session.commit()
            await session.refresh(existing_document)
            document = existing_document
        else:
            # Create new document
            # Determine document type based on connector
            doc_type = DocumentType.FILE
            if connector and connector.get("type") == DocumentType.GOOGLE_DRIVE_FILE:
                doc_type = DocumentType.GOOGLE_DRIVE_FILE

            document = Document(
                search_space_id=search_space_id,
                title=file_name,
                document_type=doc_type,
                document_metadata={
                    "FILE_NAME": file_name,
                },
                content=summary_content,
                embedding=summary_embedding,
                chunks=chunks,
                content_hash=content_hash,
                unique_identifier_hash=primary_hash,
                blocknote_document=blocknote_json,
                updated_at=get_current_timestamp(),
                created_by_id=user_id,
                connector_id=connector.get("connector_id") if connector else None,
            )

            session.add(document)
            await session.commit()
            await session.refresh(document)

        # Log success
        await task_logger.log_task_success(
            log_entry,
            f"Successfully processed markdown file: {file_name}",
            {
                "document_id": document.id,
                "content_hash": content_hash,
                "chunks_count": len(chunks),
                "summary_length": len(summary_content),
            },
        )

        return document
    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error processing markdown file: {file_name}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        raise db_error
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to process markdown file: {file_name}",
            str(e),
            {"error_type": type(e).__name__},
        )
        raise RuntimeError(f"Failed to process file document: {e!s}") from e
