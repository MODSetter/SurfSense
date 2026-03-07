"""Celery task to detect and mark stale notifications as failed.

This task runs periodically (every 5 minutes by default) to find notifications
that are stuck in "in_progress" status but don't have an active Redis heartbeat key.
These are marked as "failed" to prevent the frontend from showing a perpetual
"syncing" or "processing" state.

It handles two notification types:
1. **connector_indexing** — connector sync tasks (Google Calendar, etc.)
2. **document_processing** — manual file uploads, YouTube videos, etc.

Additionally, it cleans up documents stuck in pending/processing state:
- For connectors: by connector_id
- For non-connector documents (FILE uploads, YouTube): by document_id from notification metadata

Detection mechanism:
- Active tasks set a Redis key with TTL (2 minutes) as a heartbeat
- A background coroutine refreshes the key every 60 seconds
- If the task/worker crashes, the Redis key expires automatically
- This cleanup task checks for in-progress notifications without a Redis heartbeat key
- Such notifications are marked as failed with O(1) batch UPDATE
- Associated documents are also marked as failed
"""

import contextlib
import json
import logging
from datetime import UTC, datetime

import redis
from sqlalchemy import and_, or_, text
from sqlalchemy.future import select

from app.celery_app import celery_app
from app.config import config
from app.db import Document, DocumentStatus, Notification
from app.tasks.celery_tasks import get_celery_session_maker

logger = logging.getLogger(__name__)

_redis_client: redis.Redis | None = None

STALE_SYNC_ERROR_MESSAGE = "Sync was interrupted unexpectedly. Please retry."
STALE_PROCESSING_ERROR_MESSAGE = "Syncing was interrupted unexpectedly. Please retry."


def get_redis_client() -> redis.Redis:
    """Get or create Redis client for heartbeat checking."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(config.REDIS_APP_URL, decode_responses=True)
    return _redis_client


def _get_heartbeat_key(notification_id: int) -> str:
    """Generate Redis key for notification heartbeat."""
    return f"indexing:heartbeat:{notification_id}"


@celery_app.task(name="cleanup_stale_indexing_notifications")
def cleanup_stale_indexing_notifications_task():
    """
    Check for stale notifications and mark them as failed.

    Handles two notification types:
    1. connector_indexing — connector sync tasks
    2. document_processing — manual file uploads, YouTube videos, etc.

    Detection: Redis heartbeat key with 2-min TTL. Missing key = stale task.
    Also marks associated pending/processing documents as failed.
    """
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(_cleanup_stale_notifications())
        loop.run_until_complete(_cleanup_stale_document_processing_notifications())
    finally:
        loop.close()


async def _cleanup_stale_notifications():
    """Find and mark stale connector indexing notifications as failed.

    Uses Redis TTL-based detection:
    1. Find all in-progress notifications with their connector_id
    2. Check which ones are missing their Redis heartbeat key
    3. Mark those as failed with O(1) batch UPDATE using JSONB || operator
    4. Mark associated documents (pending/processing) as failed
    """
    async with get_celery_session_maker()() as session:
        try:
            # Find all in-progress connector indexing notifications
            # Fetch full metadata to properly extract connector_id
            result = await session.execute(
                select(
                    Notification.id,
                    Notification.notification_metadata,
                ).where(
                    and_(
                        Notification.type == "connector_indexing",
                        Notification.notification_metadata["status"].astext
                        == "in_progress",
                    )
                )
            )
            in_progress_rows = result.fetchall()

            if not in_progress_rows:
                logger.debug("No in-progress connector indexing notifications found")
                return

            # Check which ones are missing heartbeat keys in Redis
            redis_client = get_redis_client()
            stale_notification_ids = []
            stale_connector_ids = []

            for row in in_progress_rows:
                notification_id = row[0]
                metadata = row[1]  # Full metadata dict
                heartbeat_key = _get_heartbeat_key(notification_id)
                if not redis_client.exists(heartbeat_key):
                    stale_notification_ids.append(notification_id)
                    # Extract connector_id from metadata dict for document cleanup
                    if metadata and isinstance(metadata, dict):
                        connector_id = metadata.get("connector_id")
                        logger.debug(
                            f"Notification {notification_id} metadata: {metadata}, "
                            f"connector_id: {connector_id}"
                        )
                        if connector_id is not None:
                            with contextlib.suppress(ValueError, TypeError):
                                stale_connector_ids.append(int(connector_id))

            if not stale_notification_ids:
                logger.debug(
                    f"All {len(in_progress_rows)} in-progress notifications have active Redis heartbeats"
                )
                return

            logger.warning(
                f"Found {len(stale_notification_ids)} stale connector indexing notifications "
                f"(no Redis heartbeat key): {stale_notification_ids}"
            )
            logger.info(f"Connector IDs for document cleanup: {stale_connector_ids}")

            # O(1) Batch UPDATE notifications using JSONB || operator
            # This merges the update data into existing notification_metadata
            # Also updates title and message for proper UI display
            update_data = {
                "status": "failed",
                "completed_at": datetime.now(UTC).isoformat(),
                "error_message": STALE_SYNC_ERROR_MESSAGE,
                "sync_stage": "failed",
            }

            await session.execute(
                text("""
                    UPDATE notifications 
                    SET metadata = metadata || CAST(:update_json AS jsonb),
                        title = 'Failed: ' || COALESCE(metadata->>'connector_name', 'Connector'),
                        message = :display_message
                    WHERE id = ANY(:ids)
                """),
                {
                    "update_json": json.dumps(update_data),
                    "display_message": STALE_SYNC_ERROR_MESSAGE,
                    "ids": stale_notification_ids,
                },
            )

            logger.info(
                f"Successfully marked {len(stale_notification_ids)} stale notifications as failed"
            )

            # ===== Clean up stuck documents for stale connectors =====
            if stale_connector_ids:
                await _cleanup_stuck_documents(session, stale_connector_ids)

            await session.commit()

        except Exception as e:
            logger.error(f"Error cleaning up stale notifications: {e!s}", exc_info=True)
            await session.rollback()


async def _cleanup_stuck_documents(session, connector_ids: list[int]):
    """
    Mark documents stuck in pending/processing state as failed for given connectors.

    This ensures that when a connector sync is interrupted, all partially-processed
    documents are marked with a clear error state instead of being stuck indefinitely.

    Args:
        session: Database session
        connector_ids: List of connector IDs whose documents should be cleaned up
    """
    if not connector_ids:
        return

    try:
        # Count documents that will be affected (for logging)
        count_result = await session.execute(
            select(Document.id).where(
                and_(
                    Document.connector_id.in_(connector_ids),
                    or_(
                        Document.status["state"].astext == DocumentStatus.PENDING,
                        Document.status["state"].astext == DocumentStatus.PROCESSING,
                    ),
                )
            )
        )
        stuck_doc_ids = [row[0] for row in count_result.fetchall()]

        if not stuck_doc_ids:
            logger.debug(f"No stuck documents found for connector IDs: {connector_ids}")
            return

        logger.warning(
            f"Found {len(stuck_doc_ids)} stuck documents (pending/processing) "
            f"for connector IDs {connector_ids}: {stuck_doc_ids[:20]}..."  # Log first 20
        )

        # O(1) Batch UPDATE: Mark all stuck documents as failed using JSONB
        # The error message matches what we show in notifications
        failed_status = DocumentStatus.failed(STALE_SYNC_ERROR_MESSAGE)

        await session.execute(
            text("""
                UPDATE documents 
                SET status = CAST(:failed_status AS jsonb),
                    updated_at = :now
                WHERE connector_id = ANY(:connector_ids)
                  AND (
                      status->>'state' = :pending_state
                      OR status->>'state' = :processing_state
                  )
            """),
            {
                "failed_status": json.dumps(failed_status),
                "now": datetime.now(UTC),
                "connector_ids": connector_ids,
                "pending_state": DocumentStatus.PENDING,
                "processing_state": DocumentStatus.PROCESSING,
            },
        )

        logger.info(
            f"Successfully marked {len(stuck_doc_ids)} stuck documents as failed "
            f"for connector IDs: {connector_ids}"
        )

    except Exception as e:
        logger.error(
            f"Error cleaning up stuck documents for connectors {connector_ids}: {e!s}",
            exc_info=True,
        )
        # Don't raise - let the notification cleanup continue even if document cleanup fails


# ===== Document Processing Cleanup (FILE uploads, YouTube, etc.) =====


async def _cleanup_stale_document_processing_notifications():
    """Find and mark stale document processing notifications as failed.

    Same Redis heartbeat mechanism as connector indexing cleanup, but for
    document_processing type notifications (FILE uploads, YouTube videos, etc.).

    For each stale notification that contains a document_id in its metadata,
    the associated document is also marked as failed.
    """
    async with get_celery_session_maker()() as session:
        try:
            # Find all in-progress document processing notifications
            result = await session.execute(
                select(
                    Notification.id,
                    Notification.notification_metadata,
                ).where(
                    and_(
                        Notification.type == "document_processing",
                        Notification.notification_metadata["status"].astext
                        == "in_progress",
                    )
                )
            )
            in_progress_rows = result.fetchall()

            if not in_progress_rows:
                logger.debug("No in-progress document processing notifications found")
                return

            # Check which ones are missing heartbeat keys in Redis
            redis_client = get_redis_client()
            stale_notification_ids = []
            stale_document_ids = []

            for row in in_progress_rows:
                notification_id = row[0]
                metadata = row[1]  # Full metadata dict
                heartbeat_key = _get_heartbeat_key(notification_id)
                if not redis_client.exists(heartbeat_key):
                    stale_notification_ids.append(notification_id)
                    # Extract document_id from metadata for document cleanup
                    if metadata and isinstance(metadata, dict):
                        doc_id = metadata.get("document_id")
                        if doc_id is not None:
                            with contextlib.suppress(ValueError, TypeError):
                                stale_document_ids.append(int(doc_id))

            if not stale_notification_ids:
                logger.debug(
                    f"All {len(in_progress_rows)} in-progress document processing "
                    "notifications have active Redis heartbeats"
                )
                return

            logger.warning(
                f"Found {len(stale_notification_ids)} stale document processing "
                f"notifications (no Redis heartbeat): {stale_notification_ids}"
            )

            # O(1) Batch UPDATE: Mark stale notifications as failed
            update_data = {
                "status": "failed",
                "completed_at": datetime.now(UTC).isoformat(),
                "error_message": STALE_PROCESSING_ERROR_MESSAGE,
                "processing_stage": "failed",
            }

            await session.execute(
                text("""
                    UPDATE notifications
                    SET metadata = metadata || CAST(:update_json AS jsonb),
                        title = 'Failed: ' || COALESCE(metadata->>'document_name', 'Document'),
                        message = :display_message
                    WHERE id = ANY(:ids)
                """),
                {
                    "update_json": json.dumps(update_data),
                    "display_message": STALE_PROCESSING_ERROR_MESSAGE,
                    "ids": stale_notification_ids,
                },
            )

            logger.info(
                f"Successfully marked {len(stale_notification_ids)} stale document "
                "processing notifications as failed"
            )

            # Clean up stuck documents by document_id from notification metadata
            if stale_document_ids:
                await _cleanup_stuck_non_connector_documents(
                    session, stale_document_ids
                )

            await session.commit()

        except Exception as e:
            logger.error(
                f"Error cleaning up stale document processing notifications: {e!s}",
                exc_info=True,
            )
            await session.rollback()


async def _cleanup_stuck_non_connector_documents(session, document_ids: list[int]):
    """
    Mark specific non-connector documents stuck in pending/processing as failed.

    These are documents (FILE uploads, YouTube, etc.) identified from stale
    notification metadata. Only documents that are still in pending/processing
    state are updated — already-completed documents are left untouched.

    Args:
        session: Database session
        document_ids: List of document IDs to check and potentially mark as failed
    """
    if not document_ids:
        return

    try:
        # Find which of these documents are actually stuck
        count_result = await session.execute(
            select(Document.id).where(
                and_(
                    Document.id.in_(document_ids),
                    or_(
                        Document.status["state"].astext == DocumentStatus.PENDING,
                        Document.status["state"].astext == DocumentStatus.PROCESSING,
                    ),
                )
            )
        )
        stuck_doc_ids = [row[0] for row in count_result.fetchall()]

        if not stuck_doc_ids:
            logger.debug(
                f"No stuck non-connector documents found for IDs: {document_ids}"
            )
            return

        logger.warning(
            f"Found {len(stuck_doc_ids)} stuck non-connector documents "
            f"(pending/processing): {stuck_doc_ids}"
        )

        failed_status = DocumentStatus.failed(STALE_PROCESSING_ERROR_MESSAGE)

        await session.execute(
            text("""
                UPDATE documents
                SET status = CAST(:failed_status AS jsonb),
                    updated_at = :now
                WHERE id = ANY(:doc_ids)
                  AND (
                      status->>'state' = :pending_state
                      OR status->>'state' = :processing_state
                  )
            """),
            {
                "failed_status": json.dumps(failed_status),
                "now": datetime.now(UTC),
                "doc_ids": stuck_doc_ids,
                "pending_state": DocumentStatus.PENDING,
                "processing_state": DocumentStatus.PROCESSING,
            },
        )

        logger.info(
            f"Successfully marked {len(stuck_doc_ids)} stuck non-connector "
            "documents as failed"
        )

    except Exception as e:
        logger.error(
            f"Error cleaning up stuck non-connector documents {document_ids}: {e!s}",
            exc_info=True,
        )
        # Don't raise — let the rest of the cleanup continue
