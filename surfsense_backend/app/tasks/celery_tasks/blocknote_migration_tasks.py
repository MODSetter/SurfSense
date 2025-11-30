"""Celery tasks for populating blocknote_document for existing documents."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload
from sqlalchemy.pool import NullPool

from app.celery_app import celery_app
from app.config import config
from app.db import Document
from app.utils.blocknote_converter import convert_markdown_to_blocknote

logger = logging.getLogger(__name__)


def get_celery_session_maker():
    """
    Create a new async session maker for Celery tasks.
    This is necessary because Celery tasks run in a new event loop,
    and the default session maker is bound to the main app's event loop.
    """
    engine = create_async_engine(
        config.DATABASE_URL,
        poolclass=NullPool,
        echo=False,
    )
    return async_sessionmaker(engine, expire_on_commit=False)


@celery_app.task(name="populate_blocknote_for_documents", bind=True)
def populate_blocknote_for_documents_task(
    self, document_ids: list[int] | None = None, batch_size: int = 50
):
    """
    Celery task to populate blocknote_document for existing documents.

    Args:
        document_ids: Optional list of specific document IDs to process.
                     If None, processes all documents with blocknote_document IS NULL.
        batch_size: Number of documents to process in each batch (default: 50)
    """
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(
            _populate_blocknote_for_documents(document_ids, batch_size)
        )
    finally:
        loop.close()


async def _populate_blocknote_for_documents(
    document_ids: list[int] | None = None, batch_size: int = 50
):
    """
    Async function to populate blocknote_document for documents.

    Args:
        document_ids: Optional list of specific document IDs to process
        batch_size: Number of documents to process per batch
    """
    async with get_celery_session_maker()() as session:
        try:
            # Build query for documents that need blocknote_document populated
            query = select(Document).where(Document.blocknote_document.is_(None))

            # If specific document IDs provided, filter by them
            if document_ids:
                query = query.where(Document.id.in_(document_ids))

            # Load chunks relationship to avoid N+1 queries
            query = query.options(selectinload(Document.chunks))

            # Execute query
            result = await session.execute(query)
            documents = result.scalars().all()

            total_documents = len(documents)
            logger.info(f"Found {total_documents} documents to process")

            if total_documents == 0:
                logger.info("No documents to process")
                return

            # Process documents in batches
            processed = 0
            failed = 0

            for i in range(0, total_documents, batch_size):
                batch = documents[i : i + batch_size]
                logger.info(
                    f"Processing batch {i // batch_size + 1}: documents {i + 1}-{min(i + batch_size, total_documents)}"
                )

                for document in batch:
                    try:
                        # Use preloaded chunks from selectinload - no need to query again
                        chunks = sorted(document.chunks, key=lambda c: c.id)

                        if not chunks:
                            logger.warning(
                                f"Document {document.id} ({document.title}) has no chunks, skipping"
                            )
                            failed += 1
                            continue

                        # Reconstruct markdown by concatenating chunk contents
                        markdown_content = "\n\n".join(
                            chunk.content for chunk in chunks
                        )

                        if not markdown_content or not markdown_content.strip():
                            logger.warning(
                                f"Document {document.id} ({document.title}) has empty markdown content, skipping"
                            )
                            failed += 1
                            continue

                        # Convert markdown to BlockNote JSON
                        blocknote_json = await convert_markdown_to_blocknote(
                            markdown_content
                        )

                        if not blocknote_json:
                            logger.warning(
                                f"Failed to convert markdown to BlockNote for document {document.id} ({document.title})"
                            )
                            failed += 1
                            continue

                        # Update document with blocknote_document (other fields already have correct defaults)
                        document.blocknote_document = blocknote_json

                        processed += 1

                        # Commit every batch_size documents to avoid long transactions
                        if processed % batch_size == 0:
                            await session.commit()
                            logger.info(
                                f"Committed batch: {processed} documents processed so far"
                            )

                    except Exception as e:
                        logger.error(
                            f"Error processing document {document.id} ({document.title}): {e}",
                            exc_info=True,
                        )
                        failed += 1
                        # Continue with next document instead of failing entire batch
                        continue

                # Commit remaining changes in the batch
                await session.commit()
                logger.info(f"Completed batch {i // batch_size + 1}")

            logger.info(
                f"Migration complete: {processed} documents processed, {failed} failed"
            )

        except Exception as e:
            await session.rollback()
            logger.error(f"Error in blocknote migration task: {e}", exc_info=True)
            raise
