"""Celery task to detect and mark stale connector indexing notifications as failed.

This task runs periodically (every 5 minutes by default) to find notifications
that are stuck in "in_progress" status but haven't received a heartbeat update
in the configured timeout period. These are marked as "failed" to prevent the
frontend from showing a perpetual "syncing" state.
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.future import select
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.pool import NullPool

from app.celery_app import celery_app
from app.config import config
from app.db import Notification

logger = logging.getLogger(__name__)

# Timeout in minutes - notifications without heartbeat for this long are marked as failed
# Should be longer than HEARTBEAT_INTERVAL_SECONDS (30s) * a reasonable number of missed heartbeats
# 5 minutes = 10 missed heartbeats, which is a reasonable threshold
STALE_NOTIFICATION_TIMEOUT_MINUTES = 5


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
    - Have updated_at older than STALE_NOTIFICATION_TIMEOUT_MINUTES

    And marks them as failed with an appropriate error message.
    """
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(_cleanup_stale_notifications())
    finally:
        loop.close()


async def _cleanup_stale_notifications():
    """Find and mark stale connector indexing notifications as failed."""
    async with get_celery_session_maker()() as session:
        try:
            # Calculate the cutoff time
            cutoff_time = datetime.now(UTC) - timedelta(
                minutes=STALE_NOTIFICATION_TIMEOUT_MINUTES
            )

            # Find stale notifications:
            # - type = 'connector_indexing'
            # - metadata->>'status' = 'in_progress'
            # - updated_at < cutoff_time
            result = await session.execute(
                select(Notification).filter(
                    and_(
                        Notification.type == "connector_indexing",
                        Notification.notification_metadata["status"].astext
                        == "in_progress",
                        Notification.updated_at < cutoff_time,
                    )
                )
            )
            stale_notifications = result.scalars().all()

            if not stale_notifications:
                logger.debug("No stale connector indexing notifications found")
                return

            logger.warning(
                f"Found {len(stale_notifications)} stale connector indexing notifications "
                f"(no heartbeat for >{STALE_NOTIFICATION_TIMEOUT_MINUTES} minutes)"
            )

            # Mark each stale notification as failed
            for notification in stale_notifications:
                try:
                    # Get current indexed count from metadata if available
                    indexed_count = notification.notification_metadata.get(
                        "indexed_count", 0
                    )
                    connector_name = notification.notification_metadata.get(
                        "connector_name", "Unknown"
                    )

                    # Calculate how long it's been stale
                    stale_duration = datetime.now(UTC) - notification.updated_at
                    stale_minutes = int(stale_duration.total_seconds() / 60)

                    # Update notification metadata
                    notification.notification_metadata["status"] = "failed"
                    notification.notification_metadata["completed_at"] = datetime.now(
                        UTC
                    ).isoformat()
                    notification.notification_metadata["error_message"] = (
                        f"Indexing task appears to have crashed or timed out. "
                        f"No activity detected for {stale_minutes} minutes. "
                        f"Please try syncing again."
                    )

                    # Flag the JSONB column as modified for SQLAlchemy to detect the change
                    flag_modified(notification, "notification_metadata")

                    logger.info(
                        f"Marking notification {notification.id} for connector '{connector_name}' as failed "
                        f"(stale for {stale_minutes} minutes, indexed {indexed_count} items before failure)"
                    )

                except Exception as e:
                    logger.error(
                        f"Error marking notification {notification.id} as failed: {e!s}",
                        exc_info=True,
                    )
                    continue

            # Commit all changes
            await session.commit()
            logger.info(
                f"Successfully marked {len(stale_notifications)} stale notifications as failed"
            )

        except Exception as e:
            logger.error(f"Error cleaning up stale notifications: {e!s}", exc_info=True)
            await session.rollback()
