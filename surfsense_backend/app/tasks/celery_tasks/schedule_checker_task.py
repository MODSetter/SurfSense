"""Meta-scheduler task that checks for connectors needing periodic indexing."""

import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.future import select
from sqlalchemy.pool import NullPool

from app.celery_app import celery_app
from app.config import config
from app.db import SearchSourceConnector, SearchSourceConnectorType

logger = logging.getLogger(__name__)


def get_celery_session_maker():
    """Create async session maker for Celery tasks."""
    engine = create_async_engine(
        config.DATABASE_URL,
        poolclass=NullPool,
        echo=False,
    )
    return async_sessionmaker(engine, expire_on_commit=False)


@celery_app.task(name="check_periodic_schedules")
def check_periodic_schedules_task():
    """
    Check all connectors for periodic indexing that's due.
    This task runs every minute and triggers indexing for any connector
    whose next_scheduled_at time has passed.
    """
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(_check_and_trigger_schedules())
    finally:
        loop.close()


async def _check_and_trigger_schedules():
    """Check database for connectors that need indexing and trigger their tasks."""
    async with get_celery_session_maker()() as session:
        try:
            # Find all connectors with periodic indexing enabled that are due
            now = datetime.now(UTC)
            result = await session.execute(
                select(SearchSourceConnector).filter(
                    SearchSourceConnector.periodic_indexing_enabled == True,  # noqa: E712
                    SearchSourceConnector.next_scheduled_at <= now,
                )
            )
            due_connectors = result.scalars().all()

            if not due_connectors:
                logger.debug("No connectors due for periodic indexing")
                return

            logger.info(f"Found {len(due_connectors)} connectors due for indexing")

            # Import all indexing tasks
            from app.tasks.celery_tasks.connector_tasks import (
                index_airtable_records_task,
                index_clickup_tasks_task,
                index_composio_connector_task,
                index_confluence_pages_task,
                index_crawled_urls_task,
                index_discord_messages_task,
                index_elasticsearch_documents_task,
                index_github_repos_task,
                index_google_calendar_events_task,
                index_google_drive_files_task,
                index_google_gmail_messages_task,
                index_jira_issues_task,
                index_linear_issues_task,
                index_luma_events_task,
                index_notion_pages_task,
                index_slack_messages_task,
            )

            # Map connector types to their tasks
            task_map = {
                SearchSourceConnectorType.SLACK_CONNECTOR: index_slack_messages_task,
                SearchSourceConnectorType.NOTION_CONNECTOR: index_notion_pages_task,
                SearchSourceConnectorType.GITHUB_CONNECTOR: index_github_repos_task,
                SearchSourceConnectorType.LINEAR_CONNECTOR: index_linear_issues_task,
                SearchSourceConnectorType.JIRA_CONNECTOR: index_jira_issues_task,
                SearchSourceConnectorType.CONFLUENCE_CONNECTOR: index_confluence_pages_task,
                SearchSourceConnectorType.CLICKUP_CONNECTOR: index_clickup_tasks_task,
                SearchSourceConnectorType.GOOGLE_CALENDAR_CONNECTOR: index_google_calendar_events_task,
                SearchSourceConnectorType.AIRTABLE_CONNECTOR: index_airtable_records_task,
                SearchSourceConnectorType.GOOGLE_GMAIL_CONNECTOR: index_google_gmail_messages_task,
                SearchSourceConnectorType.DISCORD_CONNECTOR: index_discord_messages_task,
                SearchSourceConnectorType.LUMA_CONNECTOR: index_luma_events_task,
                SearchSourceConnectorType.ELASTICSEARCH_CONNECTOR: index_elasticsearch_documents_task,
                SearchSourceConnectorType.WEBCRAWLER_CONNECTOR: index_crawled_urls_task,
                SearchSourceConnectorType.GOOGLE_DRIVE_CONNECTOR: index_google_drive_files_task,
                # Composio connector types
                SearchSourceConnectorType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR: index_composio_connector_task,
                SearchSourceConnectorType.COMPOSIO_GMAIL_CONNECTOR: index_composio_connector_task,
                SearchSourceConnectorType.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR: index_composio_connector_task,
            }

            # Trigger indexing for each due connector
            for connector in due_connectors:
                task = task_map.get(connector.connector_type)
                if task:
                    logger.info(
                        f"Triggering periodic indexing for connector {connector.id} "
                        f"({connector.connector_type.value})"
                    )

                    # Special handling for Google Drive - uses config for folder/file selection
                    if (
                        connector.connector_type
                        == SearchSourceConnectorType.GOOGLE_DRIVE_CONNECTOR
                    ):
                        connector_config = connector.config or {}
                        selected_folders = connector_config.get("selected_folders", [])
                        selected_files = connector_config.get("selected_files", [])
                        indexing_options = connector_config.get(
                            "indexing_options",
                            {
                                "max_files_per_folder": 100,
                                "incremental_sync": True,
                                "include_subfolders": True,
                            },
                        )

                        if selected_folders or selected_files:
                            task.delay(
                                connector.id,
                                connector.search_space_id,
                                str(connector.user_id),
                                {
                                    "folders": selected_folders,
                                    "files": selected_files,
                                    "indexing_options": indexing_options,
                                },
                            )
                        else:
                            # No folders/files selected - skip indexing but still update next_scheduled_at
                            # to prevent checking every minute
                            logger.info(
                                f"Google Drive connector {connector.id} has no folders or files selected, "
                                "skipping periodic indexing (will check again at next scheduled time)"
                            )
                            from datetime import timedelta

                            connector.next_scheduled_at = now + timedelta(
                                minutes=connector.indexing_frequency_minutes
                            )
                            await session.commit()
                            continue

                    # Special handling for Webcrawler - skip if no URLs configured
                    elif (
                        connector.connector_type
                        == SearchSourceConnectorType.WEBCRAWLER_CONNECTOR
                    ):
                        from app.utils.webcrawler_utils import parse_webcrawler_urls

                        connector_config = connector.config or {}
                        urls = parse_webcrawler_urls(
                            connector_config.get("INITIAL_URLS")
                        )

                        if urls:
                            task.delay(
                                connector.id,
                                connector.search_space_id,
                                str(connector.user_id),
                                None,  # start_date
                                None,  # end_date
                            )
                        else:
                            # No URLs configured - skip indexing but still update next_scheduled_at
                            logger.info(
                                f"Webcrawler connector {connector.id} has no URLs configured, "
                                "skipping periodic indexing (will check again at next scheduled time)"
                            )
                            from datetime import timedelta

                            connector.next_scheduled_at = now + timedelta(
                                minutes=connector.indexing_frequency_minutes
                            )
                            await session.commit()
                            continue

                    else:
                        task.delay(
                            connector.id,
                            connector.search_space_id,
                            str(connector.user_id),
                            None,  # start_date - uses last_indexed_at
                            None,  # end_date - uses now
                        )

                    # Update next_scheduled_at for next run
                    from datetime import timedelta

                    connector.next_scheduled_at = now + timedelta(
                        minutes=connector.indexing_frequency_minutes
                    )
                    await session.commit()
                else:
                    logger.warning(
                        f"No task found for connector type {connector.connector_type}"
                    )

        except Exception as e:
            logger.error(f"Error checking periodic schedules: {e!s}", exc_info=True)
            await session.rollback()
