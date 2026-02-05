"""Celery task to detect and mark stale connector indexing notifications as failed.

This task runs periodically (every 5 minutes by default) to find notifications
that are stuck in "in_progress" status but don't have an active Redis heartbeat key.
These are marked as "failed" to prevent the frontend from showing a perpetual "syncing" state.

Detection mechanism:
- Active indexing tasks set a Redis key with TTL (2 minutes) as a heartbeat
- If the task crashes, the Redis key expires automatically
- This cleanup task checks for in-progress notifications without a Redis heartbeat key
- Such notifications are marked as failed with O(1) batch UPDATE
"""

import json
import logging
import os
from datetime import UTC, datetime

import redis
from sqlalchemy import and_, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.future import select
from sqlalchemy.pool import NullPool

from app.celery_app import celery_app
from app.config import config
from app.db import Notification

logger = logging.getLogger(__name__)

# Redis client for checking heartbeats
_redis_client: redis.Redis | None = None


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
    1. Find all in-progress notifications
    2. Check which ones are missing their Redis heartbeat key
    3. Mark those as failed with O(1) batch UPDATE using JSONB || operator
    """
    async with get_celery_session_maker()() as session:
        try:
            # Find all in-progress connector indexing notifications
            result = await session.execute(
                select(Notification.id).where(
                    and_(
                        Notification.type == "connector_indexing",
                        Notification.notification_metadata["status"].astext
                        == "in_progress",
                    )
                )
            )
            in_progress_ids = [row[0] for row in result.fetchall()]

            if not in_progress_ids:
                logger.debug("No in-progress connector indexing notifications found")
                return

            # Check which ones are missing heartbeat keys in Redis
            redis_client = get_redis_client()
            stale_notification_ids = []

            for notification_id in in_progress_ids:
                heartbeat_key = _get_heartbeat_key(notification_id)
                if not redis_client.exists(heartbeat_key):
                    stale_notification_ids.append(notification_id)

            if not stale_notification_ids:
                logger.debug(
                    f"All {len(in_progress_ids)} in-progress notifications have active Redis heartbeats"
                )
                return

            logger.warning(
                f"Found {len(stale_notification_ids)} stale connector indexing notifications "
                f"(no Redis heartbeat key): {stale_notification_ids}"
            )

            # O(1) Batch UPDATE using JSONB || operator
            # This merges the update data into existing notification_metadata
            # Also updates title and message for proper UI display
            error_message = (
                "Something went wrong while syncing your content. Please retry."
            )

            update_data = {
                "status": "failed",
                "completed_at": datetime.now(UTC).isoformat(),
                "error_message": error_message,
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
                    "display_message": f"{error_message}",
                    "ids": stale_notification_ids,
                },
            )

            await session.commit()
            logger.info(
                f"Successfully marked {len(stale_notification_ids)} stale notifications as failed (batch UPDATE)"
            )

        except Exception as e:
            logger.error(f"Error cleaning up stale notifications: {e!s}", exc_info=True)
            await session.rollback()
