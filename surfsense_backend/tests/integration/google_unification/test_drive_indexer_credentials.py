"""Integration tests: Drive indexer credential resolution for Composio vs native connectors.

Exercises ``index_google_drive_files`` with a real PostgreSQL database
containing seeded connector records.  Google API and Composio SDK are
mocked at their system boundaries.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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

_COMPOSIO_ACCOUNT_ID = "composio-test-account-123"
_INDEXER_MODULE = "app.tasks.connector_indexers.google_drive_indexer"


@pytest_asyncio.fixture
async def committed_drive_connector(async_engine):
    data = await seed_connector(
        async_engine,
        connector_type=SearchSourceConnectorType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR,
        config={"composio_connected_account_id": _COMPOSIO_ACCOUNT_ID},
        name_prefix="drive-composio",
    )
    yield data
    await cleanup_space(async_engine, data["search_space_id"])


@pytest_asyncio.fixture
async def committed_native_drive_connector(async_engine):
    data = await seed_connector(
        async_engine,
        connector_type=SearchSourceConnectorType.GOOGLE_DRIVE_CONNECTOR,
        config={
            "token": "fake-token",
            "refresh_token": "fake-refresh",
            "client_id": "fake-client-id",
            "client_secret": "fake-secret",
            "token_uri": "https://oauth2.googleapis.com/token",
        },
        name_prefix="drive-native",
    )
    yield data
    await cleanup_space(async_engine, data["search_space_id"])


@pytest_asyncio.fixture
async def committed_composio_no_account_id(async_engine):
    data = await seed_connector(
        async_engine,
        connector_type=SearchSourceConnectorType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR,
        config={},
        name_prefix="drive-noid",
    )
    yield data
    await cleanup_space(async_engine, data["search_space_id"])


@patch(f"{_INDEXER_MODULE}.TaskLoggingService")
@patch(f"{_INDEXER_MODULE}.GoogleDriveClient")
@patch(f"{_INDEXER_MODULE}.build_composio_credentials")
async def test_composio_connector_uses_composio_credentials(
    mock_build_creds,
    mock_client_cls,
    mock_task_logger_cls,
    async_engine,
    committed_drive_connector,
):
    """Drive indexer calls build_composio_credentials for a Composio connector
    and passes the result to GoogleDriveClient."""
    from app.tasks.connector_indexers.google_drive_indexer import (
        index_google_drive_files,
    )

    data = committed_drive_connector
    mock_creds = MagicMock(name="composio-credentials")
    mock_build_creds.return_value = mock_creds
    mock_task_logger_cls.return_value = mock_task_logger()

    maker = make_session_factory(async_engine)
    async with maker() as session:
        await index_google_drive_files(
            session=session,
            connector_id=data["connector_id"],
            search_space_id=data["search_space_id"],
            user_id=data["user_id"],
            folder_id="test-folder-id",
        )

    mock_build_creds.assert_called_once_with(_COMPOSIO_ACCOUNT_ID)
    mock_client_cls.assert_called_once()
    _, kwargs = mock_client_cls.call_args
    assert kwargs.get("credentials") is mock_creds


@patch(f"{_INDEXER_MODULE}.TaskLoggingService")
@patch(f"{_INDEXER_MODULE}.build_composio_credentials")
async def test_composio_connector_without_account_id_returns_error(
    mock_build_creds,
    mock_task_logger_cls,
    async_engine,
    committed_composio_no_account_id,
):
    """Drive indexer returns an error when Composio connector lacks connected_account_id."""
    from app.tasks.connector_indexers.google_drive_indexer import (
        index_google_drive_files,
    )

    data = committed_composio_no_account_id
    mock_task_logger_cls.return_value = mock_task_logger()

    maker = make_session_factory(async_engine)
    async with maker() as session:
        count, _skipped, error, _unsupported = await index_google_drive_files(
            session=session,
            connector_id=data["connector_id"],
            search_space_id=data["search_space_id"],
            user_id=data["user_id"],
            folder_id="test-folder-id",
        )

    assert count == 0
    assert error is not None
    assert (
        "composio_connected_account_id" in error.lower() or "composio" in error.lower()
    )
    mock_build_creds.assert_not_called()


@patch(f"{_INDEXER_MODULE}.TaskLoggingService")
@patch(f"{_INDEXER_MODULE}.GoogleDriveClient")
@patch(f"{_INDEXER_MODULE}.build_composio_credentials")
async def test_native_connector_does_not_use_composio_credentials(
    mock_build_creds,
    mock_client_cls,
    mock_task_logger_cls,
    async_engine,
    committed_native_drive_connector,
):
    """Drive indexer does NOT call build_composio_credentials for a native connector."""
    from app.tasks.connector_indexers.google_drive_indexer import (
        index_google_drive_files,
    )

    data = committed_native_drive_connector
    mock_task_logger_cls.return_value = mock_task_logger()

    maker = make_session_factory(async_engine)
    async with maker() as session:
        await index_google_drive_files(
            session=session,
            connector_id=data["connector_id"],
            search_space_id=data["search_space_id"],
            user_id=data["user_id"],
            folder_id="test-folder-id",
        )

    mock_build_creds.assert_not_called()
    mock_client_cls.assert_called_once()
    _, kwargs = mock_client_cls.call_args
    assert kwargs.get("credentials") is None
