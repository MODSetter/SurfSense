"""
Base functionality and shared imports for document processors.
"""

from datetime import UTC, datetime

from langchain_community.document_transformers import MarkdownifyTransformer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import Document

# Initialize markdown transformer
md = MarkdownifyTransformer()


def safe_set_chunks(document: Document, chunks: list) -> None:
    """
    Safely assign chunks to a document without triggering lazy loading.

    ALWAYS use this instead of `document.chunks = chunks` to avoid
    SQLAlchemy async errors (MissingGreenlet / greenlet_spawn).

    Why this is needed:
    - Direct assignment `document.chunks = chunks` triggers SQLAlchemy to
      load the OLD chunks first (for comparison/orphan detection)
    - This lazy loading fails in async context with asyncpg driver
    - set_committed_value bypasses this by setting the value directly

    This function is safe regardless of how the document was loaded
    (with or without selectinload).

    Args:
        document: The Document object to update
        chunks: List of Chunk objects to assign

    Example:
        # Instead of: document.chunks = chunks (DANGEROUS!)
        safe_set_chunks(document, chunks)  # Always safe
    """
    from sqlalchemy.orm import object_session
    from sqlalchemy.orm.attributes import set_committed_value

    # Keep relationship assignment lazy-load-safe.
    set_committed_value(document, "chunks", chunks)

    # Ensure chunk rows are actually persisted.
    # set_committed_value bypasses normal unit-of-work tracking, so we need to
    # explicitly attach chunk objects to the current session.
    session = object_session(document)
    if session is not None:
        if document.id is not None:
            for chunk in chunks:
                chunk.document_id = document.id
        session.add_all(chunks)


def get_current_timestamp() -> datetime:
    """
    Get the current timestamp with timezone for updated_at field.

    Returns:
        Current datetime with UTC timezone
    """
    return datetime.now(UTC)


async def check_duplicate_document(
    session: AsyncSession, content_hash: str
) -> Document | None:
    """
    Check if a document with the given content hash already exists.

    Args:
        session: Database session
        content_hash: Hash of the document content

    Returns:
        Existing document if found, None otherwise
    """
    existing_doc_result = await session.execute(
        select(Document).where(Document.content_hash == content_hash)
    )
    return existing_doc_result.scalars().first()


async def check_document_by_unique_identifier(
    session: AsyncSession, unique_identifier_hash: str
) -> Document | None:
    """
    Check if a document with the given unique identifier hash already exists.
    Eagerly loads chunks to avoid lazy loading issues during updates.

    Args:
        session: Database session
        unique_identifier_hash: Hash of the unique identifier from the source

    Returns:
        Existing document if found, None otherwise
    """
    from sqlalchemy.orm import selectinload

    existing_doc_result = await session.execute(
        select(Document)
        .options(selectinload(Document.chunks))
        .where(Document.unique_identifier_hash == unique_identifier_hash)
    )
    return existing_doc_result.scalars().first()
