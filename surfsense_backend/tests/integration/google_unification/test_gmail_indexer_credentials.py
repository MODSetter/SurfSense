"""Integration tests: Gmail indexer credential resolution for Composio vs native connectors.

Exercises ``index_google_gmail_messages`` with a real PostgreSQL database
containing seeded connector records.  Google API and Composio SDK are
mocked at their system boundaries.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

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

_COMPOSIO_ACCOUNT_ID = "composio-gmail-test-456"
_INDEXER_MODULE = "app.tasks.connector_indexers.google_gmail_indexer"


@pytest_asyncio.fixture
async def composio_gmail(async_engine):
    data = await seed_connector(
        async_engine,
        connector_type=SearchSourceConnectorType.COMPOSIO_GMAIL_CONNECTOR,
        config={"composio_connected_account_id": _COMPOSIO_ACCOUNT_ID},
        name_prefix="gmail-composio",
    )
    yield data
    await cleanup_space(async_engine, data["search_space_id"])


@pytest_asyncio.fixture
async def composio_gmail_no_id(async_engine):
    data = await seed_connector(
        async_engine,
        connector_type=SearchSourceConnectorType.COMPOSIO_GMAIL_CONNECTOR,
        config={},
        name_prefix="gmail-noid",
    )
    yield data
    await cleanup_space(async_engine, data["search_space_id"])


@pytest_asyncio.fixture
async def native_gmail(async_engine):
    data = await seed_connector(
        async_engine,
        connector_type=SearchSourceConnectorType.GOOGLE_GMAIL_CONNECTOR,
        config={
            "token": "fake",
            "refresh_token": "fake",
            "client_id": "fake",
            "client_secret": "fake",
            "token_uri": "https://oauth2.googleapis.com/token",
        },
        name_prefix="gmail-native",
    )
    yield data
    await cleanup_space(async_engine, data["search_space_id"])


@patch(f"{_INDEXER_MODULE}.TaskLoggingService")
@patch(f"{_INDEXER_MODULE}.GoogleGmailConnector")
@patch(f"{_INDEXER_MODULE}.build_composio_credentials")
async def test_composio_gmail_uses_composio_credentials(
    mock_build_creds,
    mock_gmail_cls,
    mock_tl_cls,
    async_engine,
    composio_gmail,
):
    """Gmail indexer calls build_composio_credentials for a Composio connector."""
    from app.tasks.connector_indexers.google_gmail_indexer import (
        index_google_gmail_messages,
    )

    data = composio_gmail
    mock_creds = MagicMock(name="composio-creds")
    mock_build_creds.return_value = mock_creds
    mock_tl_cls.return_value = mock_task_logger()

    mock_gmail_instance = MagicMock()
    mock_gmail_instance.get_recent_messages = AsyncMock(return_value=([], None))
    mock_gmail_cls.return_value = mock_gmail_instance

    maker = make_session_factory(async_engine)
    async with maker() as session:
        await index_google_gmail_messages(
            session=session,
            connector_id=data["connector_id"],
            search_space_id=data["search_space_id"],
            user_id=data["user_id"],
        )

    mock_build_creds.assert_called_once_with(_COMPOSIO_ACCOUNT_ID)
    mock_gmail_cls.assert_called_once()
    args, _ = mock_gmail_cls.call_args
    assert args[0] is mock_creds


@patch(f"{_INDEXER_MODULE}.TaskLoggingService")
@patch(f"{_INDEXER_MODULE}.build_composio_credentials")
async def test_composio_gmail_without_account_id_returns_error(
    mock_build_creds,
    mock_tl_cls,
    async_engine,
    composio_gmail_no_id,
):
    """Gmail indexer returns error when Composio connector lacks connected_account_id."""
    from app.tasks.connector_indexers.google_gmail_indexer import (
        index_google_gmail_messages,
    )

    data = composio_gmail_no_id
    mock_tl_cls.return_value = mock_task_logger()

    maker = make_session_factory(async_engine)
    async with maker() as session:
        count, _skipped, error = await index_google_gmail_messages(
            session=session,
            connector_id=data["connector_id"],
            search_space_id=data["search_space_id"],
            user_id=data["user_id"],
        )

    assert count == 0
    assert error is not None
    assert "composio" in error.lower()
    mock_build_creds.assert_not_called()


@patch(f"{_INDEXER_MODULE}.TaskLoggingService")
@patch(f"{_INDEXER_MODULE}.GoogleGmailConnector")
@patch(f"{_INDEXER_MODULE}.build_composio_credentials")
async def test_native_gmail_does_not_use_composio_credentials(
    mock_build_creds,
    mock_gmail_cls,
    mock_tl_cls,
    async_engine,
    native_gmail,
):
    """Gmail indexer does NOT call build_composio_credentials for a native connector."""
    from app.tasks.connector_indexers.google_gmail_indexer import (
        index_google_gmail_messages,
    )

    data = native_gmail
    mock_tl_cls.return_value = mock_task_logger()

    mock_gmail_instance = MagicMock()
    mock_gmail_instance.get_recent_messages = AsyncMock(return_value=([], None))
    mock_gmail_cls.return_value = mock_gmail_instance

    maker = make_session_factory(async_engine)
    async with maker() as session:
        await index_google_gmail_messages(
            session=session,
            connector_id=data["connector_id"],
            search_space_id=data["search_space_id"],
            user_id=data["user_id"],
        )

    mock_build_creds.assert_not_called()
