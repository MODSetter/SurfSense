"""
Circleback meeting document processor.

This module processes meeting data received from Circleback webhooks
and stores it as searchable documents in the database.
"""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    Document,
    DocumentType,
    SearchSourceConnector,
    SearchSourceConnectorType,
    SearchSpace,
)
from app.services.llm_service import get_document_summary_llm
from app.utils.document_converters import (
    create_document_chunks,
    generate_content_hash,
    generate_document_summary,
    generate_unique_identifier_hash,
)

from .base import (
    check_document_by_unique_identifier,
    get_current_timestamp,
)

logger = logging.getLogger(__name__)


async def add_circleback_meeting_document(
    session: AsyncSession,
    meeting_id: int,
    meeting_name: str,
    markdown_content: str,
    metadata: dict[str, Any],
    search_space_id: int,
    connector_id: int | None = None,
) -> Document | None:
    """
    Process and store a Circleback meeting document.

    Args:
        session: Database session
        meeting_id: Circleback meeting ID
        meeting_name: Name of the meeting
        markdown_content: Meeting content formatted as markdown
        metadata: Meeting metadata dictionary
        search_space_id: ID of the search space
        connector_id: ID of the Circleback connector (for deletion support)

    Returns:
        Document object if successful, None if failed or duplicate
    """
    try:
        # Generate unique identifier hash using Circleback meeting ID
        unique_identifier = f"circleback_{meeting_id}"
        unique_identifier_hash = generate_unique_identifier_hash(
            DocumentType.CIRCLEBACK, unique_identifier, search_space_id
        )

        # Generate content hash
        content_hash = generate_content_hash(markdown_content, search_space_id)

        # Check if document with this unique identifier already exists
        existing_document = await check_document_by_unique_identifier(
            session, unique_identifier_hash
        )

        if existing_document:
            # Document exists - check if content has changed
            if existing_document.content_hash == content_hash:
                logger.info(f"Circleback meeting {meeting_id} unchanged. Skipping.")
                return existing_document
            else:
                # Content has changed - update the existing document
                logger.info(
                    f"Content changed for Circleback meeting {meeting_id}. Updating document."
                )

        # Get LLM for generating summary
        llm = await get_document_summary_llm(session, search_space_id)
        if not llm:
            logger.warning(
                f"No LLM configured for search space {search_space_id}. Using content as summary."
            )
            # Use first 1000 chars as summary if no LLM available
            summary_content = (
                markdown_content[:1000] + "..."
                if len(markdown_content) > 1000
                else markdown_content
            )
            summary_embedding = None
        else:
            # Generate summary with metadata
            document_metadata = {
                "meeting_name": meeting_name,
                "meeting_id": meeting_id,
                "document_type": "Circleback Meeting",
                **{
                    k: v
                    for k, v in metadata.items()
                    if isinstance(v, str | int | float | bool)
                },
            }
            summary_content, summary_embedding = await generate_document_summary(
                markdown_content, llm, document_metadata
            )

        # Process chunks
        chunks = await create_document_chunks(markdown_content)

        # Convert to BlockNote JSON for editing capability
        from app.utils.blocknote_converter import convert_markdown_to_blocknote

        blocknote_json = await convert_markdown_to_blocknote(markdown_content)
        if not blocknote_json:
            logger.warning(
                f"Failed to convert Circleback meeting {meeting_id} to BlockNote JSON, document will not be editable"
            )

        # Prepare document metadata
        document_metadata = {
            "CIRCLEBACK_MEETING_ID": meeting_id,
            "MEETING_NAME": meeting_name,
            "SOURCE": "CIRCLEBACK_WEBHOOK",
            **metadata,
        }

        # Fetch the user who set up the Circleback connector (preferred)
        # or fall back to search space owner if no connector found
        created_by_user_id = None

        # Try to find the Circleback connector for this search space
        connector_result = await session.execute(
            select(SearchSourceConnector.user_id).where(
                SearchSourceConnector.search_space_id == search_space_id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.CIRCLEBACK_CONNECTOR,
            )
        )
        connector_user = connector_result.scalar_one_or_none()

        if connector_user:
            # Use the user who set up the Circleback connector
            created_by_user_id = connector_user
        else:
            # Fallback: use search space owner if no connector found
            search_space_result = await session.execute(
                select(SearchSpace.user_id).where(SearchSpace.id == search_space_id)
            )
            created_by_user_id = search_space_result.scalar_one_or_none()

        # Update or create document
        if existing_document:
            # Update existing document
            existing_document.title = meeting_name
            existing_document.content = summary_content
            existing_document.content_hash = content_hash
            if summary_embedding is not None:
                existing_document.embedding = summary_embedding
            existing_document.document_metadata = document_metadata
            existing_document.chunks = chunks
            existing_document.blocknote_document = blocknote_json
            existing_document.content_needs_reindexing = False
            existing_document.updated_at = get_current_timestamp()
            # Ensure connector_id is set (backfill for documents created before this field)
            if connector_id is not None:
                existing_document.connector_id = connector_id

            await session.commit()
            await session.refresh(existing_document)
            document = existing_document
            logger.info(
                f"Updated Circleback meeting document {meeting_id} in search space {search_space_id}"
            )
        else:
            # Create new document
            document = Document(
                search_space_id=search_space_id,
                title=meeting_name,
                document_type=DocumentType.CIRCLEBACK,
                document_metadata=document_metadata,
                content=summary_content,
                embedding=summary_embedding,
                chunks=chunks,
                content_hash=content_hash,
                unique_identifier_hash=unique_identifier_hash,
                blocknote_document=blocknote_json,
                content_needs_reindexing=False,
                updated_at=get_current_timestamp(),
                created_by_id=created_by_user_id,
                connector_id=connector_id,
            )

            session.add(document)
            await session.commit()
            await session.refresh(document)
            logger.info(
                f"Created new Circleback meeting document {meeting_id} in search space {search_space_id}"
            )

        return document

    except SQLAlchemyError as db_error:
        await session.rollback()
        logger.error(
            f"Database error processing Circleback meeting {meeting_id}: {db_error}"
        )
        raise db_error
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to process Circleback meeting {meeting_id}: {e!s}")
        raise RuntimeError(f"Failed to process Circleback meeting: {e!s}") from e
