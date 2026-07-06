"""
Extension document processor for SurfSense browser extension.
"""

import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, DocumentType
from app.schemas import ExtensionDocumentContent
from app.services.task_logging_service import TaskLoggingService
from app.utils.document_converters import (
    create_document_chunks,
    embed_text,
    generate_content_hash,
    generate_unique_identifier_hash,
)

from .base import (
    check_document_by_unique_identifier,
    get_current_timestamp,
    safe_set_chunks,
)


async def add_extension_received_document(
    session: AsyncSession,
    content: ExtensionDocumentContent,
    workspace_id: int,
    user_id: str,
) -> Document | None:
    """
    Process and store document content received from the SurfSense Extension.

    Args:
        session: Database session
        content: Document content from extension
        workspace_id: ID of the workspace
        user_id: ID of the user

    Returns:
        Document object if successful, None if failed
    """
    task_logger = TaskLoggingService(session, workspace_id)

    # Log task start
    log_entry = await task_logger.log_task_start(
        task_name="extension_document",
        source="background_task",
        message=f"Processing extension document: {content.metadata.VisitedWebPageTitle}",
        metadata={
            "url": content.metadata.VisitedWebPageURL,
            "title": content.metadata.VisitedWebPageTitle,
            "user_id": str(user_id),
        },
    )

    try:
        # Format document metadata in a more maintainable way
        metadata_sections = [
            (
                "METADATA",
                [
                    f"SESSION_ID: {content.metadata.BrowsingSessionId}",
                    f"URL: {content.metadata.VisitedWebPageURL}",
                    f"TITLE: {content.metadata.VisitedWebPageTitle}",
                    f"REFERRER: {content.metadata.VisitedWebPageReffererURL}",
                    f"TIMESTAMP: {content.metadata.VisitedWebPageDateWithTimeInISOString}",
                    f"DURATION_MS: {content.metadata.VisitedWebPageVisitDurationInMilliseconds}",
                ],
            ),
            (
                "CONTENT",
                ["FORMAT: markdown", "TEXT_START", content.page_content, "TEXT_END"],
            ),
        ]

        # Build the document string more efficiently
        document_parts = []
        document_parts.append("<DOCUMENT>")

        for section_title, section_content in metadata_sections:
            document_parts.append(f"<{section_title}>")
            document_parts.extend(section_content)
            document_parts.append(f"</{section_title}>")

        document_parts.append("</DOCUMENT>")
        combined_document_string = "\n".join(document_parts)

        # Generate unique identifier hash for this extension document (using URL)
        unique_identifier_hash = generate_unique_identifier_hash(
            DocumentType.EXTENSION, content.metadata.VisitedWebPageURL, workspace_id
        )

        # Generate content hash
        content_hash = generate_content_hash(combined_document_string, workspace_id)

        # Check if document with this unique identifier already exists
        existing_document = await check_document_by_unique_identifier(
            session, unique_identifier_hash
        )

        if existing_document:
            # Document exists - check if content has changed
            if existing_document.content_hash == content_hash:
                await task_logger.log_task_success(
                    log_entry,
                    f"Extension document unchanged: {content.metadata.VisitedWebPageTitle}",
                    {
                        "duplicate_detected": True,
                        "existing_document_id": existing_document.id,
                    },
                )
                logging.info(
                    f"Document for URL {content.metadata.VisitedWebPageURL} unchanged. Skipping."
                )
                return existing_document
            else:
                # Content has changed - update the existing document
                logging.info(
                    f"Content changed for URL {content.metadata.VisitedWebPageURL}. Updating document."
                )

        summary_content = combined_document_string
        summary_embedding = embed_text(summary_content)

        # Process chunks
        chunks = await create_document_chunks(content.page_content)

        # Update or create document
        if existing_document:
            # Update existing document
            existing_document.title = content.metadata.VisitedWebPageTitle
            existing_document.content = summary_content
            existing_document.content_hash = content_hash
            existing_document.embedding = summary_embedding
            existing_document.document_metadata = content.metadata.model_dump()
            await safe_set_chunks(session, existing_document, chunks)
            existing_document.source_markdown = combined_document_string
            existing_document.updated_at = get_current_timestamp()

            await session.commit()
            await session.refresh(existing_document)
            document = existing_document
        else:
            # Create new document
            document = Document(
                workspace_id=workspace_id,
                title=content.metadata.VisitedWebPageTitle,
                document_type=DocumentType.EXTENSION,
                document_metadata=content.metadata.model_dump(),
                content=summary_content,
                embedding=summary_embedding,
                chunks=chunks,
                content_hash=content_hash,
                unique_identifier_hash=unique_identifier_hash,
                source_markdown=combined_document_string,
                updated_at=get_current_timestamp(),
                created_by_id=user_id,
            )

            session.add(document)
            await session.commit()
            await session.refresh(document)

        # Log success
        await task_logger.log_task_success(
            log_entry,
            f"Successfully processed extension document: {content.metadata.VisitedWebPageTitle}",
            {
                "document_id": document.id,
                "content_hash": content_hash,
                "url": content.metadata.VisitedWebPageURL,
            },
        )

        return document

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error processing extension document: {content.metadata.VisitedWebPageTitle}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        raise db_error
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to process extension document: {content.metadata.VisitedWebPageTitle}",
            str(e),
            {"error_type": type(e).__name__},
        )
        raise RuntimeError(f"Failed to process extension document: {e!s}") from e
