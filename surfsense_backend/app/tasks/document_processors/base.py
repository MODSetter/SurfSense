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


async def safe_set_chunks(
    session: "AsyncSession", document: Document, chunks: list
) -> None:
    """
    Delete old chunks and assign new ones to a document.

    This replaces direct ``document.chunks = chunks`` which triggers lazy
    loading (and MissingGreenlet errors in async contexts).  It also
    explicitly deletes pre-existing chunks so they don't accumulate across
    repeated re-indexes — ``set_committed_value`` bypasses SQLAlchemy's
    delete-orphan cascade.

    Args:
        session: The current async database session.
        document: The Document object to update.
        chunks: List of Chunk objects to assign.
    """
    from sqlalchemy import delete
    from sqlalchemy.orm.attributes import set_committed_value

    from app.db import Chunk

    if document.id is not None:
        await session.execute(delete(Chunk).where(Chunk.document_id == document.id))
        for chunk in chunks:
            chunk.document_id = document.id

    set_committed_value(document, "chunks", chunks)
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
