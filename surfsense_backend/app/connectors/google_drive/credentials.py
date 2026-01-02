"""Google Drive OAuth credential management."""

import json
from datetime import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm.attributes import flag_modified

from app.db import SearchSourceConnector


async def get_valid_credentials(
    session: AsyncSession,
    connector_id: int,
) -> Credentials:
    """
    Get valid Google OAuth credentials, refreshing if needed.

    Args:
        session: Database session
        connector_id: Connector ID

    Returns:
        Valid Google OAuth credentials

    Raises:
        ValueError: If credentials are missing or invalid
        Exception: If token refresh fails
    """
    result = await session.execute(
        select(SearchSourceConnector).filter(SearchSourceConnector.id == connector_id)
    )
    connector = result.scalars().first()

    if not connector:
        raise ValueError(f"Connector {connector_id} not found")

    config_data = connector.config
    exp = config_data.get("expiry", "").replace("Z", "")

    if not all(
        [
            config_data.get("client_id"),
            config_data.get("client_secret"),
            config_data.get("refresh_token"),
        ]
    ):
        raise ValueError(
            "Google OAuth credentials (client_id, client_secret, refresh_token) must be set"
        )

    credentials = Credentials(
        token=config_data.get("token"),
        refresh_token=config_data.get("refresh_token"),
        token_uri=config_data.get("token_uri"),
        client_id=config_data.get("client_id"),
        client_secret=config_data.get("client_secret"),
        scopes=config_data.get("scopes", []),
        expiry=datetime.fromisoformat(exp) if exp else None,
    )

    if credentials.expired or not credentials.valid:
        try:
            credentials.refresh(Request())

            connector.config = json.loads(credentials.to_json())
            flag_modified(connector, "config")
            await session.commit()

        except Exception as e:
            raise Exception(f"Failed to refresh Google OAuth credentials: {e!s}") from e

    return credentials


def validate_credentials(credentials: Credentials) -> bool:
    """
    Validate that credentials have required fields.

    Args:
        credentials: Google OAuth credentials

    Returns:
        True if valid, False otherwise
    """
    return all(
        [
            credentials.client_id,
            credentials.client_secret,
            credentials.refresh_token,
        ]
    )
