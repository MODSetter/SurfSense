"""
Connector Scheduler Service

This service manages automated scheduling and execution of connector syncs.
It runs as a background service to check for due schedules and execute them.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import config
from app.db import (
    ConnectorSchedule,
    SearchSourceConnector,
    SearchSourceConnectorType,
    get_async_session,
)
from app.services.task_logging_service import TaskLoggingService
from app.tasks.connector_indexers import (
    index_airtable_records,
    index_clickup_tasks,
    index_confluence_pages,
    index_discord_messages,
    index_github_repos,
    index_google_calendar_events,
    index_google_gmail_messages,
    index_jira_issues,
    index_linear_issues,
    index_luma_events,
    index_notion_pages,
    index_slack_messages,
)
from app.utils.schedule_helpers import calculate_next_run

logger = logging.getLogger(__name__)


class ConnectorSchedulerService:
    """Service for managing automated connector scheduling and execution."""

    def __init__(self):
        self.running = False
        self.check_interval = 60  # Check every 60 seconds
        self.max_concurrent_jobs = 5  # Maximum concurrent indexing jobs
        self.active_jobs: Dict[int, asyncio.Task] = {}

        # Mapping of connector types to their indexer functions
        self.connector_indexers = {
            SearchSourceConnectorType.SLACK_CONNECTOR: index_slack_messages,
            SearchSourceConnectorType.NOTION_CONNECTOR: index_notion_pages,
            SearchSourceConnectorType.GITHUB_CONNECTOR: index_github_repos,
            SearchSourceConnectorType.LINEAR_CONNECTOR: index_linear_issues,
            SearchSourceConnectorType.JIRA_CONNECTOR: index_jira_issues,
            SearchSourceConnectorType.CONFLUENCE_CONNECTOR: index_confluence_pages,
            SearchSourceConnectorType.DISCORD_CONNECTOR: index_discord_messages,
            SearchSourceConnectorType.CLICKUP_CONNECTOR: index_clickup_tasks,
            SearchSourceConnectorType.GOOGLE_CALENDAR_CONNECTOR: index_google_calendar_events,
            SearchSourceConnectorType.GOOGLE_GMAIL_CONNECTOR: index_google_gmail_messages,
            SearchSourceConnectorType.AIRTABLE_CONNECTOR: index_airtable_records,
            SearchSourceConnectorType.LUMA_CONNECTOR: index_luma_events,
        }

    async def start(self):
        """Start the scheduler service."""
        if self.running:
            logger.warning("Scheduler service is already running")
            return

        self.running = True
        logger.info("Starting connector scheduler service...")

        try:
            while self.running:
                await self._check_and_execute_schedules()
                await asyncio.sleep(self.check_interval)
        except Exception as e:
            logger.error(f"Scheduler service error: {e}", exc_info=True)
        finally:
            self.running = False
            logger.info("Connector scheduler service stopped")

    async def stop(self):
        """Stop the scheduler service."""
        logger.info("Stopping connector scheduler service...")
        self.running = False

        # Cancel all active jobs
        for job_id, task in self.active_jobs.items():
            if not task.done():
                task.cancel()
                logger.info(f"Cancelled active job {job_id}")

        self.active_jobs.clear()

    async def _check_and_execute_schedules(self):
        """Check for due schedules and execute them."""
        try:
            async with get_async_session() as session:
                # Get all active schedules that are due
                due_schedules = await self._get_due_schedules(session)

                if not due_schedules:
                    return

                logger.info(f"Found {len(due_schedules)} due schedules")

                for schedule in due_schedules:
                    if len(self.active_jobs) >= self.max_concurrent_jobs:
                        logger.warning(
                            f"Maximum concurrent jobs ({self.max_concurrent_jobs}) reached, "
                            f"skipping schedule {schedule.id}"
                        )
                        break

                    # Execute schedule in background
                    await self._execute_schedule(schedule, session)

        except Exception as e:
            logger.error(f"Error checking schedules: {e}", exc_info=True)

    async def _get_due_schedules(self, session: AsyncSession) -> List[ConnectorSchedule]:
        """Get all schedules that are due for execution."""
        now = datetime.now(datetime.utc)

        query = (
            select(ConnectorSchedule)
            .options(
                selectinload(ConnectorSchedule.connector),
                selectinload(ConnectorSchedule.search_space),
            )
            .filter(
                ConnectorSchedule.is_active == True,  # noqa: E712
                ConnectorSchedule.next_run_at <= now,
            )
            .order_by(ConnectorSchedule.next_run_at)
        )

        result = await session.execute(query)
        return result.scalars().all()

    async def _execute_schedule(
        self, schedule: ConnectorSchedule, session: AsyncSession
    ):
        """Execute a scheduled connector sync."""
        schedule_id = schedule.id

        try:
            # Check if we already have an active job for this schedule
            if schedule_id in self.active_jobs and not self.active_jobs[schedule_id].done():
                logger.warning(f"Schedule {schedule_id} is already running, skipping")
                return

            # Update last_run_at before starting
            await self._update_schedule_last_run(session, schedule_id)

            # Get the appropriate indexer function
            indexer_func = self.connector_indexers.get(schedule.connector.connector_type)
            if not indexer_func:
                logger.error(
                    f"No indexer function found for connector type: {schedule.connector.connector_type}"
                )
                await self._update_schedule_next_run(session, schedule)
                return

            # Create a new session for the background task
            async with get_async_session() as background_session:
                # Start the indexing task
                task = asyncio.create_task(
                    self._run_indexing_task(
                        background_session,
                        schedule,
                        indexer_func,
                    )
                )
                self.active_jobs[schedule_id] = task

                logger.info(
                    f"Started scheduled indexing for connector {schedule.connector.name} "
                    f"(schedule {schedule_id})"
                )

        except Exception as e:
            logger.error(
                f"Error executing schedule {schedule_id}: {e}", exc_info=True
            )
            await self._update_schedule_next_run(session, schedule)

    async def _run_indexing_task(
        self,
        session: AsyncSession,
        schedule: ConnectorSchedule,
        indexer_func,
    ):
        """Run the actual indexing task for a schedule."""
        schedule_id = schedule.id
        connector = schedule.connector

        try:
            # Create a task log entry
            task_logger = TaskLoggingService(session, schedule.search_space_id)
            log_entry = await task_logger.log_task_start(
                f"scheduled_sync_{connector.connector_type.value}",
                "connector_scheduler",
                f"Scheduled sync for {connector.name}",
                {
                    "schedule_id": schedule_id,
                    "connector_id": connector.id,
                    "connector_type": connector.connector_type.value,
                    "search_space_id": schedule.search_space_id,
                },
            )

            # Calculate date range for incremental sync
            start_date = None
            if connector.last_indexed_at:
                # Start from last indexed date minus 1 day for overlap
                start_date = (connector.last_indexed_at - timedelta(days=1)).strftime(
                    "%Y-%m-%d"
                )

            end_date = datetime.now(datetime.utc).strftime("%Y-%m-%d")

            # Execute the indexer function
            documents_processed, error_message = await indexer_func(
                session=session,
                connector_id=connector.id,
                search_space_id=schedule.search_space_id,
                user_id=str(connector.user_id),
                start_date=start_date,
                end_date=end_date,
                update_last_indexed=True,
            )

            if error_message:
                await task_logger.log_task_failure(
                    log_entry,
                    f"Scheduled sync failed for {connector.name}",
                    error_message,
                    {"documents_processed": documents_processed},
                )
                logger.error(
                    f"Scheduled sync failed for connector {connector.name}: {error_message}"
                )
            else:
                await task_logger.log_task_success(
                    log_entry,
                    f"Scheduled sync completed for {connector.name}",
                    {"documents_processed": documents_processed},
                )
                logger.info(
                    f"Scheduled sync completed for connector {connector.name}: "
                    f"{documents_processed} documents processed"
                )

            # Update next run time
            async with get_async_session() as update_session:
                await self._update_schedule_next_run(update_session, schedule)

        except Exception as e:
            logger.error(
                f"Error in scheduled indexing task for schedule {schedule_id}: {e}",
                exc_info=True,
            )
            # Update next run time even on error to prevent stuck schedules
            async with get_async_session() as update_session:
                await self._update_schedule_next_run(update_session, schedule)
        finally:
            # Remove from active jobs
            self.active_jobs.pop(schedule_id, None)

    async def _update_schedule_last_run(self, session: AsyncSession, schedule_id: int):
        """Update the last_run_at timestamp for a schedule."""
        await session.execute(
            update(ConnectorSchedule)
            .filter(ConnectorSchedule.id == schedule_id)
            .values(last_run_at=datetime.now(timezone.utc))
        )
        await session.commit()

    async def _update_schedule_next_run(
        self, session: AsyncSession, schedule: ConnectorSchedule
    ):
        """Update the next_run_at timestamp for a schedule."""
        next_run = calculate_next_run(
            schedule.schedule_type, 
            schedule.cron_expression,
            schedule.daily_time,
            schedule.weekly_day,
            schedule.weekly_time,
            schedule.hourly_minute
        )

        await session.execute(
            update(ConnectorSchedule)
            .filter(ConnectorSchedule.id == schedule.id)
            .values(next_run_at=next_run)
        )
        await session.commit()

        logger.info(
            f"Updated next run time for schedule {schedule.id} to {next_run}"
        )

    async def get_scheduler_status(self) -> dict:
        """Get the current status of the scheduler service."""
        return {
            "running": self.running,
            "active_jobs": len(self.active_jobs),
            "max_concurrent_jobs": self.max_concurrent_jobs,
            "check_interval": self.check_interval,
            "active_job_details": {
                str(schedule_id): {
                    "running": not task.done(),
                    "done": task.done(),
                    "cancelled": task.cancelled(),
                }
                for schedule_id, task in self.active_jobs.items()
            },
        }

    async def force_execute_schedule(self, schedule_id: int) -> bool:
        """Force execution of a specific schedule (for testing/manual triggers)."""
        try:
            async with get_async_session() as session:
                # Get the schedule
                result = await session.execute(
                    select(ConnectorSchedule)
                    .options(
                        selectinload(ConnectorSchedule.connector),
                        selectinload(ConnectorSchedule.search_space),
                    )
                    .filter(ConnectorSchedule.id == schedule_id)
                )
                schedule = result.scalars().first()

                if not schedule:
                    logger.error(f"Schedule {schedule_id} not found")
                    return False

                if not schedule.is_active:
                    logger.error(f"Schedule {schedule_id} is not active")
                    return False

                # Execute the schedule
                await self._execute_schedule(schedule, session)
                return True

        except Exception as e:
            logger.error(f"Error force executing schedule {schedule_id}: {e}")
            return False


# Global scheduler instance
_scheduler_instance: Optional[ConnectorSchedulerService] = None


async def get_scheduler() -> ConnectorSchedulerService:
    """Get the global scheduler instance."""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = ConnectorSchedulerService()
    return _scheduler_instance


async def start_scheduler():
    """Start the global scheduler service."""
    scheduler = await get_scheduler()
    await scheduler.start()


async def stop_scheduler():
    """Stop the global scheduler service."""
    global _scheduler_instance
    if _scheduler_instance:
        await _scheduler_instance.stop()
        _scheduler_instance = None
