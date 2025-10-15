"""
Base functionality and shared imports for document processors.
"""

from langchain_community.document_transformers import MarkdownifyTransformer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import Document

# Initialize markdown transformer
md = MarkdownifyTransformer()


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
