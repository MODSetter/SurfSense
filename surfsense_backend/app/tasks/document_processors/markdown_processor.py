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
)

from .base import (
    check_duplicate_document,
)


async def add_received_markdown_file_document(
    session: AsyncSession,
    file_name: str,
    file_in_markdown: str,
    search_space_id: int,
    user_id: str,
) -> Document | None:
    """
    Process and store a markdown file document.

    Args:
        session: Database session
        file_name: Name of the markdown file
        file_in_markdown: Content of the markdown file
        search_space_id: ID of the search space
        user_id: ID of the user

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
        content_hash = generate_content_hash(file_in_markdown, search_space_id)

        # Check if document with this content hash already exists
        existing_document = await check_duplicate_document(session, content_hash)
        if existing_document:
            await task_logger.log_task_success(
                log_entry,
                f"Markdown file document already exists: {file_name}",
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
        user_llm = await get_user_long_context_llm(session, user_id)
        if not user_llm:
            raise RuntimeError(f"No long context LLM configured for user {user_id}")

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

        # Create and store document
        document = Document(
            search_space_id=search_space_id,
            title=file_name,
            document_type=DocumentType.FILE,
            document_metadata={
                "FILE_NAME": file_name,
            },
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
