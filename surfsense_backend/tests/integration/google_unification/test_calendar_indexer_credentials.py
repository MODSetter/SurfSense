"""Integration tests: Calendar indexer credential resolution for Composio vs native connectors.

Exercises ``index_google_calendar_events`` with a real PostgreSQL database
containing seeded connector records.  Google API and Composio SDK are
mocked at their system boundaries.
"""

from __future__ import annotations

from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.db import SearchSourceConnectorType

from .conftest import (
    cleanup_space,
    make_session_factory,
    mock_task_logger,
    seed_connector,
)

pytestmark = pytest.mark.integration

_COMPOSIO_ACCOUNT_ID = "composio-calendar-test-789"
_INDEXER_MODULE = "app.tasks.connector_indexers.google_calendar_indexer"
_GET_ACCESS_TOKEN = "app.services.composio_service.ComposioService.get_access_token"


@pytest_asyncio.fixture
async def composio_calendar(async_engine):
    data = await seed_connector(
        async_engine,
        connector_type=SearchSourceConnectorType.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR,
        config={"composio_connected_account_id": _COMPOSIO_ACCOUNT_ID},
        name_prefix="cal-composio",
    )
    yield data
    await cleanup_space(async_engine, data["workspace_id"])


@pytest_asyncio.fixture
async def composio_calendar_no_id(async_engine):
    data = await seed_connector(
        async_engine,
        connector_type=SearchSourceConnectorType.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR,
        config={},
        name_prefix="cal-noid",
    )
    yield data
    await cleanup_space(async_engine, data["workspace_id"])


@pytest_asyncio.fixture
async def native_calendar(async_engine):
    data = await seed_connector(
        async_engine,
        connector_type=SearchSourceConnectorType.GOOGLE_CALENDAR_CONNECTOR,
        config={
            "token": "fake",
            "refresh_token": "fake",
            "client_id": "fake",
            "client_secret": "fake",
            "token_uri": "https://oauth2.googleapis.com/token",
        },
        name_prefix="cal-native",
    )
    yield data
    await cleanup_space(async_engine, data["workspace_id"])


@patch(_GET_ACCESS_TOKEN)
@patch(f"{_INDEXER_MODULE}.TaskLoggingService")
@patch(f"{_INDEXER_MODULE}.GoogleCalendarConnector")
@patch(f"{_INDEXER_MODULE}.ComposioService")
async def test_composio_calendar_uses_composio_service(
    mock_composio_service_cls,
    mock_cal_cls,
    mock_tl_cls,
    mock_get_access_token,
    async_engine,
    composio_calendar,
):
    """Calendar indexer uses Composio tools directly for a Composio connector."""
    from app.tasks.connector_indexers.google_calendar_indexer import (
        index_google_calendar_events,
    )

    data = composio_calendar
    mock_composio_service = MagicMock()
    mock_composio_service.get_calendar_events = AsyncMock(return_value=([], None))
    mock_composio_service_cls.return_value = mock_composio_service
    mock_tl_cls.return_value = mock_task_logger()

    maker = make_session_factory(async_engine)
    async with maker() as session:
        await index_google_calendar_events(
            session=session,
            connector_id=data["connector_id"],
            workspace_id=data["workspace_id"],
            user_id=data["user_id"],
        )

    mock_composio_service_cls.assert_called_once()
    mock_composio_service.get_calendar_events.assert_called_once_with(
        connected_account_id=_COMPOSIO_ACCOUNT_ID,
        entity_id=f"surfsense_{data['user_id']}",
        time_min=ANY,
        time_max=ANY,
        max_results=250,
    )
    mock_cal_cls.assert_not_called()
    mock_get_access_token.assert_not_called()


@patch(_GET_ACCESS_TOKEN)
@patch(f"{_INDEXER_MODULE}.TaskLoggingService")
@patch(f"{_INDEXER_MODULE}.ComposioService")
async def test_composio_calendar_without_account_id_returns_error(
    mock_composio_service_cls,
    mock_tl_cls,
    mock_get_access_token,
    async_engine,
    composio_calendar_no_id,
):
    """Calendar indexer returns error when Composio connector lacks connected_account_id."""
    from app.tasks.connector_indexers.google_calendar_indexer import (
        index_google_calendar_events,
    )

    data = composio_calendar_no_id
    mock_tl_cls.return_value = mock_task_logger()

    maker = make_session_factory(async_engine)
    async with maker() as session:
        count, _skipped, error = await index_google_calendar_events(
            session=session,
            connector_id=data["connector_id"],
            workspace_id=data["workspace_id"],
            user_id=data["user_id"],
        )

    assert count == 0
    assert error is not None
    assert "composio" in error.lower()
    mock_composio_service_cls.assert_not_called()
    mock_get_access_token.assert_not_called()


@patch(_GET_ACCESS_TOKEN)
@patch(f"{_INDEXER_MODULE}.TaskLoggingService")
@patch(f"{_INDEXER_MODULE}.ComposioService")
@patch(f"{_INDEXER_MODULE}.GoogleCalendarConnector")
async def test_native_calendar_uses_google_calendar_connector(
    mock_cal_cls,
    mock_composio_service_cls,
    mock_tl_cls,
    mock_get_access_token,
    async_engine,
    native_calendar,
):
    """Native Calendar connector uses GoogleCalendarConnector with no Composio path."""
    from app.tasks.connector_indexers.google_calendar_indexer import (
        index_google_calendar_events,
    )

    data = native_calendar
    mock_tl_cls.return_value = mock_task_logger()

    mock_cal_instance = MagicMock()
    mock_cal_instance.get_all_primary_calendar_events = AsyncMock(
        return_value=([], None)
    )
    mock_cal_cls.return_value = mock_cal_instance

    maker = make_session_factory(async_engine)
    async with maker() as session:
        await index_google_calendar_events(
            session=session,
            connector_id=data["connector_id"],
            workspace_id=data["workspace_id"],
            user_id=data["user_id"],
        )

    mock_cal_cls.assert_called_once()
    mock_composio_service_cls.assert_not_called()
    mock_get_access_token.assert_not_called()
