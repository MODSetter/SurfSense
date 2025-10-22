"""Celery tasks for connector indexing."""

import logging

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.celery_app import celery_app
from app.config import config

logger = logging.getLogger(__name__)


def get_celery_session_maker():
    """
    Create a new async session maker for Celery tasks.
    This is necessary because Celery tasks run in a new event loop,
    and the default session maker is bound to the main app's event loop.
    """
    engine = create_async_engine(
        config.DATABASE_URL,
        poolclass=NullPool,  # Don't use connection pooling for Celery tasks
        echo=False,
    )
    return async_sessionmaker(engine, expire_on_commit=False)


@celery_app.task(name="index_slack_messages", bind=True)
def index_slack_messages_task(
    self,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """Celery task to index Slack messages."""
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(
            _index_slack_messages(
                connector_id, search_space_id, user_id, start_date, end_date
            )
        )
    finally:
        loop.close()


async def _index_slack_messages(
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """Index Slack messages with new session."""
    from app.routes.search_source_connectors_routes import (
        run_slack_indexing,
    )

    async with get_celery_session_maker()() as session:
        await run_slack_indexing(
            session, connector_id, search_space_id, user_id, start_date, end_date
        )


@celery_app.task(name="index_notion_pages", bind=True)
def index_notion_pages_task(
    self,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """Celery task to index Notion pages."""
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(
            _index_notion_pages(
                connector_id, search_space_id, user_id, start_date, end_date
            )
        )
    finally:
        loop.close()


async def _index_notion_pages(
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """Index Notion pages with new session."""
    from app.routes.search_source_connectors_routes import (
        run_notion_indexing,
    )

    async with get_celery_session_maker()() as session:
        await run_notion_indexing(
            session, connector_id, search_space_id, user_id, start_date, end_date
        )


@celery_app.task(name="index_github_repos", bind=True)
def index_github_repos_task(
    self,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """Celery task to index GitHub repositories."""
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(
            _index_github_repos(
                connector_id, search_space_id, user_id, start_date, end_date
            )
        )
    finally:
        loop.close()


async def _index_github_repos(
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """Index GitHub repositories with new session."""
    from app.routes.search_source_connectors_routes import (
        run_github_indexing,
    )

    async with get_celery_session_maker()() as session:
        await run_github_indexing(
            session, connector_id, search_space_id, user_id, start_date, end_date
        )


@celery_app.task(name="index_linear_issues", bind=True)
def index_linear_issues_task(
    self,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """Celery task to index Linear issues."""
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(
            _index_linear_issues(
                connector_id, search_space_id, user_id, start_date, end_date
            )
        )
    finally:
        loop.close()


async def _index_linear_issues(
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """Index Linear issues with new session."""
    from app.routes.search_source_connectors_routes import (
        run_linear_indexing,
    )

    async with get_celery_session_maker()() as session:
        await run_linear_indexing(
            session, connector_id, search_space_id, user_id, start_date, end_date
        )


@celery_app.task(name="index_jira_issues", bind=True)
def index_jira_issues_task(
    self,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """Celery task to index Jira issues."""
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(
            _index_jira_issues(
                connector_id, search_space_id, user_id, start_date, end_date
            )
        )
    finally:
        loop.close()


async def _index_jira_issues(
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """Index Jira issues with new session."""
    from app.routes.search_source_connectors_routes import (
        run_jira_indexing,
    )

    async with get_celery_session_maker()() as session:
        await run_jira_indexing(
            session, connector_id, search_space_id, user_id, start_date, end_date
        )


@celery_app.task(name="index_confluence_pages", bind=True)
def index_confluence_pages_task(
    self,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """Celery task to index Confluence pages."""
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(
            _index_confluence_pages(
                connector_id, search_space_id, user_id, start_date, end_date
            )
        )
    finally:
        loop.close()


async def _index_confluence_pages(
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """Index Confluence pages with new session."""
    from app.routes.search_source_connectors_routes import (
        run_confluence_indexing,
    )

    async with get_celery_session_maker()() as session:
        await run_confluence_indexing(
            session, connector_id, search_space_id, user_id, start_date, end_date
        )


@celery_app.task(name="index_clickup_tasks", bind=True)
def index_clickup_tasks_task(
    self,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """Celery task to index ClickUp tasks."""
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(
            _index_clickup_tasks(
                connector_id, search_space_id, user_id, start_date, end_date
            )
        )
    finally:
        loop.close()


async def _index_clickup_tasks(
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """Index ClickUp tasks with new session."""
    from app.routes.search_source_connectors_routes import (
        run_clickup_indexing,
    )

    async with get_celery_session_maker()() as session:
        await run_clickup_indexing(
            session, connector_id, search_space_id, user_id, start_date, end_date
        )


@celery_app.task(name="index_google_calendar_events", bind=True)
def index_google_calendar_events_task(
    self,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """Celery task to index Google Calendar events."""
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(
            _index_google_calendar_events(
                connector_id, search_space_id, user_id, start_date, end_date
            )
        )
    finally:
        loop.close()


async def _index_google_calendar_events(
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """Index Google Calendar events with new session."""
    from app.routes.search_source_connectors_routes import (
        run_google_calendar_indexing,
    )

    async with get_celery_session_maker()() as session:
        await run_google_calendar_indexing(
            session, connector_id, search_space_id, user_id, start_date, end_date
        )


@celery_app.task(name="index_airtable_records", bind=True)
def index_airtable_records_task(
    self,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """Celery task to index Airtable records."""
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(
            _index_airtable_records(
                connector_id, search_space_id, user_id, start_date, end_date
            )
        )
    finally:
        loop.close()


async def _index_airtable_records(
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """Index Airtable records with new session."""
    from app.routes.search_source_connectors_routes import (
        run_airtable_indexing,
    )

    async with get_celery_session_maker()() as session:
        await run_airtable_indexing(
            session, connector_id, search_space_id, user_id, start_date, end_date
        )


@celery_app.task(name="index_google_gmail_messages", bind=True)
def index_google_gmail_messages_task(
    self,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """Celery task to index Google Gmail messages."""
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(
            _index_google_gmail_messages(
                connector_id, search_space_id, user_id, start_date, end_date
            )
        )
    finally:
        loop.close()


async def _index_google_gmail_messages(
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """Index Google Gmail messages with new session."""
    from datetime import datetime

    from app.routes.search_source_connectors_routes import (
        run_google_gmail_indexing,
    )

    # Parse dates to calculate days_back
    max_messages = 100
    days_back = 30  # Default

    if start_date:
        try:
            # Parse start_date (format: YYYY-MM-DD)
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            # Calculate days back from now
            days_back = (datetime.now() - start_dt).days
            # Ensure at least 1 day
            days_back = max(1, days_back)
        except ValueError:
            # If parsing fails, use default
            days_back = 30

    async with get_celery_session_maker()() as session:
        await run_google_gmail_indexing(
            session, connector_id, search_space_id, user_id, max_messages, days_back
        )


@celery_app.task(name="index_discord_messages", bind=True)
def index_discord_messages_task(
    self,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """Celery task to index Discord messages."""
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(
            _index_discord_messages(
                connector_id, search_space_id, user_id, start_date, end_date
            )
        )
    finally:
        loop.close()


async def _index_discord_messages(
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """Index Discord messages with new session."""
    from app.routes.search_source_connectors_routes import (
        run_discord_indexing,
    )

    async with get_celery_session_maker()() as session:
        await run_discord_indexing(
            session, connector_id, search_space_id, user_id, start_date, end_date
        )


@celery_app.task(name="index_luma_events", bind=True)
def index_luma_events_task(
    self,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """Celery task to index Luma events."""
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(
            _index_luma_events(
                connector_id, search_space_id, user_id, start_date, end_date
            )
        )
    finally:
        loop.close()


async def _index_luma_events(
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """Index Luma events with new session."""
    from app.routes.search_source_connectors_routes import (
        run_luma_indexing,
    )

    async with get_celery_session_maker()() as session:
        await run_luma_indexing(
            session, connector_id, search_space_id, user_id, start_date, end_date
        )


@celery_app.task(name="index_elasticsearch_documents", bind=True)
def index_elasticsearch_documents_task(
    self,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """Celery task to index Elasticsearch documents."""
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(
            _index_elasticsearch_documents(
                connector_id, search_space_id, user_id, start_date, end_date
            )
        )
    finally:
        loop.close()


async def _index_elasticsearch_documents(
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """Index Elasticsearch documents with new session."""
    from app.routes.search_source_connectors_routes import (
        run_elasticsearch_indexing,
    )

    async with get_celery_session_maker()() as session:
        await run_elasticsearch_indexing(
            session, connector_id, search_space_id, user_id, start_date, end_date
        )
