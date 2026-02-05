"""Celery task for background connector deletion.

This task handles the deletion of all documents associated with a connector
in the background, then deletes the connector itself. User is notified via
the notification system when complete (no polling required).

Features:
- Batch deletion to handle large document counts
- Automatic retry on failure
- Progress tracking via notifications
- Handles both success and failure notifications
"""

import asyncio
import logging
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.celery_app import celery_app
from app.config import config
from app.db import Document, Notification, SearchSourceConnector

logger = logging.getLogger(__name__)

# Batch size for document deletion
DELETION_BATCH_SIZE = 500


def _get_celery_session_maker():
    """Create async session maker for Celery tasks."""
    engine = create_async_engine(
        config.DATABASE_URL,
        poolclass=NullPool,
        echo=False,
    )
    return async_sessionmaker(engine, expire_on_commit=False), engine


@celery_app.task(
    bind=True,
    name="delete_connector_with_documents",
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def delete_connector_with_documents_task(
    self,
    connector_id: int,
    user_id: str,
    search_space_id: int,
    connector_name: str,
    connector_type: str,
):
    """
    Background task to delete a connector and all its associated documents.

    Creates a notification when complete (success or failure).
    No polling required - user sees notification in UI.

    Args:
        connector_id: ID of the connector to delete
        user_id: ID of the user who initiated the deletion
        search_space_id: ID of the search space
        connector_name: Name of the connector (for notification message)
        connector_type: Type of the connector (for logging)
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        return loop.run_until_complete(
            _delete_connector_async(
                connector_id=connector_id,
                user_id=user_id,
                search_space_id=search_space_id,
                connector_name=connector_name,
                connector_type=connector_type,
            )
        )
    finally:
        loop.close()


async def _delete_connector_async(
    connector_id: int,
    user_id: str,
    search_space_id: int,
    connector_name: str,
    connector_type: str,
) -> dict:
    """
    Async implementation of connector deletion.

    Steps:
    1. Count total documents to delete
    2. Delete documents in batches (chunks cascade automatically)
    3. Delete the connector record
    4. Create success notification

    On failure, creates failure notification and re-raises exception.
    """
    session_maker, engine = _get_celery_session_maker()
    total_deleted = 0

    try:
        async with session_maker() as session:
            # Step 1: Count total documents for this connector
            count_result = await session.execute(
                select(func.count(Document.id)).where(
                    Document.connector_id == connector_id
                )
            )
            total_docs = count_result.scalar() or 0

            logger.info(
                f"Starting deletion of connector {connector_id} ({connector_name}). "
                f"Documents to delete: {total_docs}"
            )

            # Step 2: Delete documents in batches
            while True:
                # Get batch of document IDs
                result = await session.execute(
                    select(Document.id)
                    .where(Document.connector_id == connector_id)
                    .limit(DELETION_BATCH_SIZE)
                )
                doc_ids = [row[0] for row in result.fetchall()]

                if not doc_ids:
                    break

                # Delete this batch (chunks are deleted via CASCADE)
                await session.execute(delete(Document).where(Document.id.in_(doc_ids)))
                await session.commit()

                total_deleted += len(doc_ids)
                logger.info(
                    f"Deleted batch of {len(doc_ids)} documents. "
                    f"Progress: {total_deleted}/{total_docs}"
                )

            # Step 3: Delete the connector record
            result = await session.execute(
                select(SearchSourceConnector).where(
                    SearchSourceConnector.id == connector_id
                )
            )
            connector = result.scalar_one_or_none()

            if connector:
                await session.delete(connector)
                logger.info(f"Deleted connector record: {connector_id}")
            else:
                logger.warning(
                    f"Connector {connector_id} not found - may have been already deleted"
                )

            # Step 4: Create success notification
            doc_text = "document" if total_deleted == 1 else "documents"
            notification = Notification(
                user_id=UUID(user_id),
                search_space_id=search_space_id,
                type="connector_deletion",
                title=f"{connector_name} removed",
                message=f"Cleanup complete. {total_deleted} {doc_text} removed.",
                notification_metadata={
                    "connector_id": connector_id,
                    "connector_name": connector_name,
                    "connector_type": connector_type,
                    "documents_deleted": total_deleted,
                    "status": "completed",
                },
            )
            session.add(notification)
            await session.commit()

            logger.info(
                f"Connector {connector_id} ({connector_name}) deleted successfully. "
                f"Total documents deleted: {total_deleted}"
            )

            return {
                "status": "success",
                "connector_id": connector_id,
                "connector_name": connector_name,
                "documents_deleted": total_deleted,
            }

    except Exception as e:
        logger.error(
            f"Failed to delete connector {connector_id} ({connector_name}): {e!s}",
            exc_info=True,
        )

        # Create failure notification
        try:
            async with session_maker() as session:
                notification = Notification(
                    user_id=UUID(user_id),
                    search_space_id=search_space_id,
                    type="connector_deletion",
                    title=f"Failed to Remove {connector_name}",
                    message="Something went wrong while removing this connector. Please try again.",
                    notification_metadata={
                        "connector_id": connector_id,
                        "connector_name": connector_name,
                        "connector_type": connector_type,
                        "documents_deleted": total_deleted,
                        "status": "failed",
                        "error": str(e),
                    },
                )
                session.add(notification)
                await session.commit()
        except Exception as notify_error:
            logger.error(
                f"Failed to create failure notification: {notify_error!s}",
                exc_info=True,
            )

        # Re-raise to trigger Celery retry
        raise

    finally:
        await engine.dispose()


async def delete_documents_by_connector_id(
    session,
    connector_id: int,
    batch_size: int = DELETION_BATCH_SIZE,
) -> int:
    """
    Delete all documents associated with a connector in batches.

    This is a utility function that can be used independently of the Celery task
    for synchronous deletion scenarios (e.g., small document counts).

    Args:
        session: AsyncSession instance
        connector_id: ID of the connector
        batch_size: Number of documents to delete per batch

    Returns:
        Total number of documents deleted
    """
    total_deleted = 0

    while True:
        result = await session.execute(
            select(Document.id)
            .where(Document.connector_id == connector_id)
            .limit(batch_size)
        )
        doc_ids = [row[0] for row in result.fetchall()]

        if not doc_ids:
            break

        await session.execute(delete(Document).where(Document.id.in_(doc_ids)))
        await session.commit()
        total_deleted += len(doc_ids)

    return total_deleted
