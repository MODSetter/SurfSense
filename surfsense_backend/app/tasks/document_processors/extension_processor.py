"""
Extension document processor for SurfSense browser extension.
"""

import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, DocumentType
from app.schemas import ExtensionDocumentContent
from app.services.llm_service import get_user_long_context_llm
from app.services.task_logging_service import TaskLoggingService
from app.utils.document_converters import (
    create_document_chunks,
    generate_content_hash,
    generate_document_summary,
)

from .base import (
    check_duplicate_document,
)


async def add_extension_received_document(
    session: AsyncSession,
    content: ExtensionDocumentContent,
    search_space_id: int,
    user_id: str,
) -> Document | None:
    """
    Process and store document content received from the SurfSense Extension.

    Args:
        session: Database session
        content: Document content from extension
        search_space_id: ID of the search space
        user_id: ID of the user

    Returns:
        Document object if successful, None if failed
    """
    task_logger = TaskLoggingService(session, search_space_id)

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
                ["FORMAT: markdown", "TEXT_START", content.pageContent, "TEXT_END"],
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
        content_hash = generate_content_hash(combined_document_string, search_space_id)

        # Check if document with this content hash already exists
        existing_document = await check_duplicate_document(session, content_hash)
        if existing_document:
            await task_logger.log_task_success(
                log_entry,
                f"Extension document already exists: {content.metadata.VisitedWebPageTitle}",
                {
                    "duplicate_detected": True,
                    "existing_document_id": existing_document.id,
                },
            )
            logging.info(
                f"Document with content hash {content_hash} already exists. Skipping processing."
            )
            return existing_document

        # Get user's long context LLM
        user_llm = await get_user_long_context_llm(session, user_id, search_space_id)
        if not user_llm:
            raise RuntimeError(
                f"No long context LLM configured for user {user_id} in search space {search_space_id}"
            )

        # Generate summary with metadata
        document_metadata = {
            "session_id": content.metadata.BrowsingSessionId,
            "url": content.metadata.VisitedWebPageURL,
            "title": content.metadata.VisitedWebPageTitle,
            "referrer": content.metadata.VisitedWebPageReffererURL,
            "timestamp": content.metadata.VisitedWebPageDateWithTimeInISOString,
            "duration_ms": content.metadata.VisitedWebPageVisitDurationInMilliseconds,
            "document_type": "Browser Extension Capture",
        }
        summary_content, summary_embedding = await generate_document_summary(
            combined_document_string, user_llm, document_metadata
        )

        # Process chunks
        chunks = await create_document_chunks(content.pageContent)

        # Create and store document
        document = Document(
            search_space_id=search_space_id,
            title=content.metadata.VisitedWebPageTitle,
            document_type=DocumentType.EXTENSION,
            document_metadata=content.metadata.model_dump(),
            content=summary_content,
            embedding=summary_embedding,
            chunks=chunks,
            content_hash=content_hash,
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
