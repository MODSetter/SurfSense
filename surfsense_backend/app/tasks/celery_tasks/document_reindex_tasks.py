"""Celery tasks for reindexing edited documents."""

import logging

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from app.celery_app import celery_app
from app.db import Document
from app.indexing_pipeline.adapters.file_upload_adapter import UploadDocumentAdapter
from app.services.llm_service import get_user_long_context_llm
from app.services.task_logging_service import TaskLoggingService
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task

logger = logging.getLogger(__name__)


@celery_app.task(name="reindex_document", bind=True)
def reindex_document_task(self, document_id: int, user_id: str):
    """
    Celery task to reindex a document after editing.

    Args:
        document_id: ID of document to reindex
        user_id: ID of user who edited the document
    """
    return run_async_celery_task(lambda: _reindex_document(document_id, user_id))


async def _reindex_document(document_id: int, user_id: str):
    """Async function to reindex a document."""
    async with get_celery_session_maker()() as session:
        result = await session.execute(
            select(Document)
            .options(selectinload(Document.chunks))
            .where(Document.id == document_id)
        )
        document = result.scalars().first()

        if not document:
            logger.error(f"Document {document_id} not found")
            return

        task_logger = TaskLoggingService(session, document.search_space_id)

        log_entry = await task_logger.log_task_start(
            task_name="document_reindex",
            source="editor",
            message=f"Starting reindex for document: {document.title}",
            metadata={
                "document_id": document_id,
                "document_type": document.document_type.value,
                "title": document.title,
                "user_id": user_id,
            },
        )

        try:
            if not document.source_markdown:
                await task_logger.log_task_failure(
                    log_entry,
                    f"Document {document_id} has no source_markdown to reindex",
                    "No source_markdown content",
                    {"error_type": "NoSourceMarkdown"},
                )
                return

            logger.info(f"Reindexing document {document_id} ({document.title})")

            user_llm = await get_user_long_context_llm(
                session, user_id, document.search_space_id
            )

            adapter = UploadDocumentAdapter(session)
            await adapter.reindex(document=document, llm=user_llm)

            await task_logger.log_task_success(
                log_entry,
                f"Successfully reindexed document: {document.title}",
                {"document_id": document_id},
            )

            logger.info(f"Successfully reindexed document {document_id}")

        except SQLAlchemyError as db_error:
            await session.rollback()
            await task_logger.log_task_failure(
                log_entry,
                f"Database error during reindex for document {document_id}",
                str(db_error),
                {"error_type": "SQLAlchemyError"},
            )
            logger.error(
                f"Database error reindexing document {document_id}: {db_error}",
                exc_info=True,
            )
            raise

        except Exception as e:
            await session.rollback()
            await task_logger.log_task_failure(
                log_entry,
                f"Failed to reindex document: {document.title}",
                str(e),
                {"error_type": type(e).__name__},
            )
            logger.error(f"Error reindexing document {document_id}: {e}", exc_info=True)
            raise
