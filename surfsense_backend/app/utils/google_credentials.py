"""Shared Google OAuth credential utilities for native and Composio connectors."""

import logging
from datetime import UTC, datetime, timedelta

from google.oauth2.credentials import Credentials

from app.db import SearchSourceConnectorType

logger = logging.getLogger(__name__)

COMPOSIO_GOOGLE_CONNECTOR_TYPES = {
    SearchSourceConnectorType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR,
    SearchSourceConnectorType.COMPOSIO_GMAIL_CONNECTOR,
    SearchSourceConnectorType.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR,
}


def build_composio_credentials(connected_account_id: str) -> Credentials:
    """
    Build Google OAuth Credentials backed by Composio's token management.

    The returned Credentials object uses a refresh_handler that fetches
    fresh access tokens from Composio on demand, so it works seamlessly
    with googleapiclient.discovery.build().
    """
    from app.services.composio_service import ComposioService

    service = ComposioService()
    access_token = service.get_access_token(connected_account_id)

    def composio_refresh_handler(request, scopes):
        fresh_token = service.get_access_token(connected_account_id)
        expiry = datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=55)
        return fresh_token, expiry

    return Credentials(
        token=access_token,
        expiry=datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=55),
        refresh_handler=composio_refresh_handler,
    )
