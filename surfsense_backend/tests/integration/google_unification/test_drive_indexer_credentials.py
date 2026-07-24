"""Integration tests: Drive indexer client + credential resolution.

Locks in the post-cea8618 architectural contract:

- Composio Drive connectors MUST use ``ComposioDriveClient`` (which routes
  through ``composio.tools.execute``) and MUST NOT depend on a raw OAuth
  access token via ``ComposioService.get_access_token``.
- Native Drive connectors MUST continue to use ``GoogleDriveClient`` with
  credentials loaded from the connector config (no Composio involvement).
- Composio Drive connectors missing ``composio_connected_account_id`` MUST
  short-circuit with a clear error before any client is constructed.

Background: prior to ``cea8618`` the Composio path used
``build_composio_credentials → GoogleDriveClient``. That broke in production
once Composio's "Mask Connected Account Secrets" project toggle was on,
because the masked token failed the ``len(access_token) >= 20`` guard in
``ComposioService.get_access_token``. The structural assertions here make
any future regression to that token-based path fail at PR time.
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

_COMPOSIO_ACCOUNT_ID = "composio-test-account-123"
_INDEXER_MODULE = "app.tasks.connector_indexers.google_drive_indexer"
_GET_ACCESS_TOKEN = "app.services.composio_service.ComposioService.get_access_token"


def _mock_drive_client(*, list_files_return: tuple = ([], None, None)) -> MagicMock:
    """Duck-typed client mock whose ``list_files`` yields the supplied tuple.

    Returning an empty file list short-circuits the indexer's full-scan
    loop after the first page so the test exercises only the
    construction + listing path, not download / ETL / DB writes.
    """
    mock = MagicMock()
    mock.list_files = AsyncMock(return_value=list_files_return)
    return mock


@pytest_asyncio.fixture
async def committed_drive_connector(async_engine):
    data = await seed_connector(
        async_engine,
        connector_type=SearchSourceConnectorType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR,
        config={"composio_connected_account_id": _COMPOSIO_ACCOUNT_ID},
        name_prefix="drive-composio",
    )
    yield data
    await cleanup_space(async_engine, data["workspace_id"])


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
    await cleanup_space(async_engine, data["workspace_id"])


@pytest_asyncio.fixture
async def committed_composio_no_account_id(async_engine):
    data = await seed_connector(
        async_engine,
        connector_type=SearchSourceConnectorType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR,
        config={},
        name_prefix="drive-noid",
    )
    yield data
    await cleanup_space(async_engine, data["workspace_id"])


@patch(_GET_ACCESS_TOKEN)
@patch(f"{_INDEXER_MODULE}.TaskLoggingService")
@patch(f"{_INDEXER_MODULE}.GoogleDriveClient")
@patch(f"{_INDEXER_MODULE}.ComposioDriveClient")
async def test_composio_drive_indexer_uses_composio_drive_client(
    mock_composio_client_cls,
    mock_native_client_cls,
    mock_task_logger_cls,
    mock_get_access_token,
    async_engine,
    committed_drive_connector,
):
    """Composio Drive must construct ComposioDriveClient and never read raw tokens.

    Reverting to the pre-cea8618 ``build_composio_credentials → GoogleDriveClient``
    path would either trip ``mock_native_client_cls.assert_not_called()`` (because
    GoogleDriveClient would be constructed) or ``mock_get_access_token.assert_not_called()``
    (because the credential builder reads the raw token).
    """
    from app.tasks.connector_indexers.google_drive_indexer import (
        index_google_drive_files,
    )

    data = committed_drive_connector
    mock_composio_client_cls.return_value = _mock_drive_client()
    mock_task_logger_cls.return_value = mock_task_logger()

    maker = make_session_factory(async_engine)
    async with maker() as session:
        await index_google_drive_files(
            session=session,
            connector_id=data["connector_id"],
            workspace_id=data["workspace_id"],
            user_id=data["user_id"],
            folder_id="test-folder-id",
        )

    mock_composio_client_cls.assert_called_once_with(
        ANY,
        data["connector_id"],
        _COMPOSIO_ACCOUNT_ID,
        entity_id=f"surfsense_{data['user_id']}",
    )
    mock_native_client_cls.assert_not_called()
    mock_get_access_token.assert_not_called()


@patch(_GET_ACCESS_TOKEN)
@patch(f"{_INDEXER_MODULE}.TaskLoggingService")
@patch(f"{_INDEXER_MODULE}.GoogleDriveClient")
@patch(f"{_INDEXER_MODULE}.ComposioDriveClient")
async def test_composio_connector_without_account_id_returns_error(
    mock_composio_client_cls,
    mock_native_client_cls,
    mock_task_logger_cls,
    mock_get_access_token,
    async_engine,
    committed_composio_no_account_id,
):
    """Missing ``composio_connected_account_id`` must short-circuit before any client construction."""
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
            workspace_id=data["workspace_id"],
            user_id=data["user_id"],
            folder_id="test-folder-id",
        )

    assert count == 0
    assert error is not None
    assert "composio" in error.lower()
    assert "connected_account_id" in error.lower()
    mock_composio_client_cls.assert_not_called()
    mock_native_client_cls.assert_not_called()
    mock_get_access_token.assert_not_called()


@patch(_GET_ACCESS_TOKEN)
@patch(f"{_INDEXER_MODULE}.TaskLoggingService")
@patch(f"{_INDEXER_MODULE}.ComposioDriveClient")
@patch(f"{_INDEXER_MODULE}.GoogleDriveClient")
async def test_native_connector_uses_google_drive_client(
    mock_native_client_cls,
    mock_composio_client_cls,
    mock_task_logger_cls,
    mock_get_access_token,
    async_engine,
    committed_native_drive_connector,
):
    """Native Drive connector must use GoogleDriveClient (no Composio involvement at all)."""
    from app.tasks.connector_indexers.google_drive_indexer import (
        index_google_drive_files,
    )

    data = committed_native_drive_connector
    mock_native_client_cls.return_value = _mock_drive_client()
    mock_task_logger_cls.return_value = mock_task_logger()

    maker = make_session_factory(async_engine)
    async with maker() as session:
        await index_google_drive_files(
            session=session,
            connector_id=data["connector_id"],
            workspace_id=data["workspace_id"],
            user_id=data["user_id"],
            folder_id="test-folder-id",
        )

    mock_native_client_cls.assert_called_once_with(ANY, data["connector_id"])
    mock_composio_client_cls.assert_not_called()
    mock_get_access_token.assert_not_called()
