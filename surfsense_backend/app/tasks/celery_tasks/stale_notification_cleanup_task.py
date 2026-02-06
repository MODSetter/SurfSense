"""Celery task to detect and mark stale connector indexing notifications as failed.

This task runs periodically (every 5 minutes by default) to find notifications
that are stuck in "in_progress" status but don't have an active Redis heartbeat key.
These are marked as "failed" to prevent the frontend from showing a perpetual "syncing" state.

Additionally, it cleans up documents stuck in pending/processing state that belong
to connectors with stale notifications.

Detection mechanism:
- Active indexing tasks set a Redis key with TTL (2 minutes) as a heartbeat
- If the task crashes, the Redis key expires automatically
- This cleanup task checks for in-progress notifications without a Redis heartbeat key
- Such notifications are marked as failed with O(1) batch UPDATE
- Documents with pending/processing status for those connectors are also marked as failed
"""

import contextlib
import json
import logging
import os
from datetime import UTC, datetime

import redis
from sqlalchemy import and_, or_, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.future import select
from sqlalchemy.pool import NullPool

from app.celery_app import celery_app
from app.config import config
from app.db import Document, DocumentStatus, Notification

logger = logging.getLogger(__name__)

# Redis client for checking heartbeats
_redis_client: redis.Redis | None = None

# Error message shown to users when sync is interrupted
STALE_SYNC_ERROR_MESSAGE = "Sync was interrupted unexpectedly. Please retry."


def get_redis_client() -> redis.Redis:
    """Get or create Redis client for heartbeat checking."""
    global _redis_client
    if _redis_client is None:
        redis_url = os.getenv(
            "REDIS_APP_URL",
            os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
        )
        _redis_client = redis.from_url(redis_url, decode_responses=True)
    return _redis_client


def _get_heartbeat_key(notification_id: int) -> str:
    """Generate Redis key for notification heartbeat."""
    return f"indexing:heartbeat:{notification_id}"


def get_celery_session_maker():
    """Create async session maker for Celery tasks."""
    engine = create_async_engine(
        config.DATABASE_URL,
        poolclass=NullPool,
        echo=False,
    )
    return async_sessionmaker(engine, expire_on_commit=False)


@celery_app.task(name="cleanup_stale_indexing_notifications")
def cleanup_stale_indexing_notifications_task():
    """
    Check for stale connector indexing notifications and mark them as failed.

    This task finds notifications that:
    - Have type = 'connector_indexing'
    - Have metadata.status = 'in_progress'
    - Do NOT have a corresponding Redis heartbeat key (meaning task crashed)

    And marks them as failed with O(1) batch UPDATE.
    Also marks associated pending/processing documents as failed.
    """
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(_cleanup_stale_notifications())
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
