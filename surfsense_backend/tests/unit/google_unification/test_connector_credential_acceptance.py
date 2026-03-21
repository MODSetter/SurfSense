"""Unit tests: Gmail, Calendar, and Drive connectors accept Composio-sourced credentials.

These tests exercise the REAL connector code with Composio-style credentials
(token + expiry + refresh_handler, but NO refresh_token / client_id / client_secret).
Only the Google API boundary (``googleapiclient.discovery.build``) is mocked.

This verifies Phase 2b: the relaxed validation in ``_get_credentials()`` correctly
allows Composio credentials through without raising ValueError or persisting to DB.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.oauth2.credentials import Credentials

pytestmark = pytest.mark.unit


def _utcnow_naive() -> datetime:
    """Return current UTC time as a naive datetime (matches google-auth convention)."""
    return datetime.now(UTC).replace(tzinfo=None)


def _composio_credentials(*, expired: bool = False) -> Credentials:
    """Create a Credentials object that mimics build_composio_credentials output."""
    if expired:
        expiry = _utcnow_naive() - timedelta(hours=1)
    else:
        expiry = _utcnow_naive() + timedelta(hours=1)

    def refresh_handler(request, scopes):
        return "refreshed-token", _utcnow_naive() + timedelta(hours=1)

    return Credentials(
        token="composio-access-token",
        expiry=expiry,
        refresh_handler=refresh_handler,
    )


# ---------------------------------------------------------------------------
# Gmail
# ---------------------------------------------------------------------------


@patch("app.connectors.google_gmail_connector.build")
async def test_gmail_accepts_valid_composio_credentials(mock_build):
    """GoogleGmailConnector.get_user_profile succeeds with Composio credentials
    that have no client_id, client_secret, or refresh_token."""
    from app.connectors.google_gmail_connector import GoogleGmailConnector

    creds = _composio_credentials(expired=False)

    mock_service = MagicMock()
    mock_service.users.return_value.getProfile.return_value.execute.return_value = {
        "emailAddress": "test@example.com",
        "messagesTotal": 42,
        "threadsTotal": 10,
        "historyId": "12345",
    }
    mock_build.return_value = mock_service

    connector = GoogleGmailConnector(
        creds,
        session=MagicMock(),
        user_id="test-user",
    )

    profile, error = await connector.get_user_profile()

    assert error is None
    assert profile["email_address"] == "test@example.com"
    mock_build.assert_called_once_with("gmail", "v1", credentials=creds)


@patch("app.connectors.google_gmail_connector.Request")
@patch("app.connectors.google_gmail_connector.build")
async def test_gmail_refreshes_expired_composio_credentials(
    mock_build, mock_request_cls
):
    """GoogleGmailConnector handles expired Composio credentials via refresh_handler
    without attempting DB persistence."""
    from app.connectors.google_gmail_connector import GoogleGmailConnector

    creds = _composio_credentials(expired=True)
    assert creds.expired

    mock_service = MagicMock()
    mock_service.users.return_value.getProfile.return_value.execute.return_value = {
        "emailAddress": "test@example.com",
        "messagesTotal": 42,
        "threadsTotal": 10,
        "historyId": "12345",
    }
    mock_build.return_value = mock_service

    mock_session = AsyncMock()
    connector = GoogleGmailConnector(
        creds,
        session=mock_session,
        user_id="test-user",
    )

    profile, error = await connector.get_user_profile()

    assert error is None
    assert profile["email_address"] == "test@example.com"
    assert creds.token == "refreshed-token"
    assert not creds.expired
    mock_session.execute.assert_not_called()
    mock_session.commit.assert_not_called()


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------


@patch("app.connectors.google_calendar_connector.build")
async def test_calendar_accepts_valid_composio_credentials(mock_build):
    """GoogleCalendarConnector.get_calendars succeeds with Composio credentials
    that have no client_id, client_secret, or refresh_token."""
    from app.connectors.google_calendar_connector import GoogleCalendarConnector

    creds = _composio_credentials(expired=False)

    mock_service = MagicMock()
    mock_service.calendarList.return_value.list.return_value.execute.return_value = {
        "items": [{"id": "primary", "summary": "My Calendar", "primary": True}],
    }
    mock_build.return_value = mock_service

    connector = GoogleCalendarConnector(
        creds,
        session=MagicMock(),
        user_id="test-user",
    )

    calendars, error = await connector.get_calendars()

    assert error is None
    assert len(calendars) == 1
    assert calendars[0]["summary"] == "My Calendar"
    mock_build.assert_called_once_with("calendar", "v3", credentials=creds)


@patch("app.connectors.google_calendar_connector.Request")
@patch("app.connectors.google_calendar_connector.build")
async def test_calendar_refreshes_expired_composio_credentials(
    mock_build, mock_request_cls
):
    """GoogleCalendarConnector handles expired Composio credentials via refresh_handler
    without attempting DB persistence."""
    from app.connectors.google_calendar_connector import GoogleCalendarConnector

    creds = _composio_credentials(expired=True)
    assert creds.expired

    mock_service = MagicMock()
    mock_service.calendarList.return_value.list.return_value.execute.return_value = {
        "items": [{"id": "primary", "summary": "My Calendar", "primary": True}],
    }
    mock_build.return_value = mock_service

    mock_session = AsyncMock()
    connector = GoogleCalendarConnector(
        creds,
        session=mock_session,
        user_id="test-user",
    )

    calendars, error = await connector.get_calendars()

    assert error is None
    assert len(calendars) == 1
    assert creds.token == "refreshed-token"
    assert not creds.expired
    mock_session.execute.assert_not_called()
    mock_session.commit.assert_not_called()


# ---------------------------------------------------------------------------
# Drive
# ---------------------------------------------------------------------------


@patch("app.connectors.google_drive.client.build")
async def test_drive_client_uses_prebuilt_composio_credentials(mock_build):
    """GoogleDriveClient with pre-built Composio credentials uses them directly,
    bypassing DB credential loading via get_valid_credentials."""
    from app.connectors.google_drive.client import GoogleDriveClient

    creds = _composio_credentials(expired=False)

    mock_service = MagicMock()
    mock_service.files.return_value.list.return_value.execute.return_value = {
        "files": [],
        "nextPageToken": None,
    }
    mock_build.return_value = mock_service

    client = GoogleDriveClient(
        session=MagicMock(),
        connector_id=999,
        credentials=creds,
    )

    files, _next_token, error = await client.list_files()

    assert error is None
    assert files == []
    mock_build.assert_called_once_with("drive", "v3", credentials=creds)


@patch("app.connectors.google_drive.client.get_valid_credentials")
@patch("app.connectors.google_drive.client.build")
async def test_drive_client_prebuilt_creds_skip_db_loading(mock_build, mock_get_valid):
    """GoogleDriveClient does NOT call get_valid_credentials when pre-built
    credentials are provided."""
    from app.connectors.google_drive.client import GoogleDriveClient

    creds = _composio_credentials(expired=False)

    mock_service = MagicMock()
    mock_service.files.return_value.list.return_value.execute.return_value = {
        "files": [],
        "nextPageToken": None,
    }
    mock_build.return_value = mock_service

    client = GoogleDriveClient(
        session=MagicMock(),
        connector_id=999,
        credentials=creds,
    )

    await client.list_files()

    mock_get_valid.assert_not_called()
