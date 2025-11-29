"""Celery tasks for reindexing edited documents."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy import delete
from sqlalchemy.orm import selectinload

from app.celery_app import celery_app
from app.config import config
from app.db import Document
from app.utils.blocknote_converter import convert_blocknote_to_markdown
from app.utils.document_converters import (
    create_document_chunks,
    generate_document_summary,
)
from app.services.llm_service import get_user_long_context_llm

logger = logging.getLogger(__name__)


def get_celery_session_maker():
    """Create async session maker for Celery tasks."""
    engine = create_async_engine(
        config.DATABASE_URL,
        poolclass=NullPool,
        echo=False,
    )
    return async_sessionmaker(engine, expire_on_commit=False)


@celery_app.task(name="reindex_document", bind=True)
def reindex_document_task(self, document_id: int, user_id: str):
    """
    Celery task to reindex a document after editing.
    
    Args:
        document_id: ID of document to reindex
        user_id: ID of user who edited the document
    """
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(_reindex_document(document_id, user_id))
    finally:
        loop.close()


async def _reindex_document(document_id: int, user_id: str):
    """Async function to reindex a document."""
    async with get_celery_session_maker()() as session:
        try:
            # Get document
            result = await session.execute(
                select(Document)
                .options(selectinload(Document.chunks))  # Eagerly load chunks
                .where(Document.id == document_id)
            )
            document = result.scalars().first()
            
            if not document:
                logger.error(f"Document {document_id} not found")
                return
            
            if not document.blocknote_document:
                logger.warning(f"Document {document_id} has no BlockNote content")
                return
            
            logger.info(f"Reindexing document {document_id} ({document.title})")
            
            # 1. Convert BlockNote → Markdown
            markdown_content = await convert_blocknote_to_markdown(
                document.blocknote_document
            )
            
            if not markdown_content:
                logger.error(f"Failed to convert document {document_id} to markdown")
                return
            
            # 2. Delete old chunks explicitly
            from app.db import Chunk
            await session.execute(
                delete(Chunk).where(Chunk.document_id == document_id)
            )
            await session.flush()  # Ensure old chunks are deleted
            
            # 3. Create new chunks
            new_chunks = await create_document_chunks(markdown_content)
            
            # 4. Add new chunks to session
            for chunk in new_chunks:
                chunk.document_id = document_id
                session.add(chunk)
            
            logger.info(f"Created {len(new_chunks)} chunks for document {document_id}")
            
            # 5. Regenerate summary
            user_llm = await get_user_long_context_llm(
                session, user_id, document.search_space_id
            )
            
            document_metadata = {
                "title": document.title,
                "document_type": document.document_type.value,
            }
            
            summary_content, summary_embedding = await generate_document_summary(
                markdown_content, user_llm, document_metadata
            )
            
            # 6. Update document
            document.content = summary_content
            document.embedding = summary_embedding
            document.content_needs_reindexing = False
            
            await session.commit()
            
            logger.info(f"Successfully reindexed document {document_id}")
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Error reindexing document {document_id}: {e}", exc_info=True)
            raise
