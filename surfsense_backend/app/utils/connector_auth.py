"""
Utility functions for connector authentication.

This module provides authentication helper functions for various connectors
to avoid circular imports between routes and connector indexers.
"""

import base64
import logging
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import SearchSourceConnector
from app.schemas.airtable_auth_credentials import AirtableAuthCredentialsBase

logger = logging.getLogger(__name__)

# Airtable OAuth endpoints
AIRTABLE_TOKEN_URL = "https://airtable.com/oauth2/v1/token"


def make_basic_auth_header(client_id: str, client_secret: str) -> str:
    """Create a Basic authentication header."""
    credentials = f"{client_id}:{client_secret}".encode()
    b64 = base64.b64encode(credentials).decode("ascii")
    return f"Basic {b64}"


async def refresh_airtable_token(
    session: AsyncSession, connector: SearchSourceConnector
):
    """
    Refresh the Airtable access token for a connector.

    Args:
        session: Database session
        connector: Airtable connector to refresh

    Returns:
        Updated connector object
    """
    try:
        logger.info(f"Refreshing Airtable token for connector {connector.id}")

        credentials = AirtableAuthCredentialsBase.from_dict(connector.config)
        auth_header = make_basic_auth_header(
            config.AIRTABLE_CLIENT_ID, config.AIRTABLE_CLIENT_SECRET
        )

        # Prepare token refresh data
        refresh_data = {
            "grant_type": "refresh_token",
            "refresh_token": credentials.refresh_token,
            "client_id": config.AIRTABLE_CLIENT_ID,
            "client_secret": config.AIRTABLE_CLIENT_SECRET,
        }

        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                AIRTABLE_TOKEN_URL,
                data=refresh_data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": auth_header,
                },
                timeout=30.0,
            )

        if token_response.status_code != 200:
            raise HTTPException(
                status_code=400, detail="Token refresh failed: {token_response.text}"
            )

        token_json = token_response.json()

        # Calculate expiration time (UTC, tz-aware)
        expires_at = None
        if token_json.get("expires_in"):
            now_utc = datetime.now(UTC)
            expires_at = now_utc + timedelta(seconds=int(token_json["expires_in"]))

        # Update credentials object
        credentials.access_token = token_json["access_token"]
        credentials.expires_in = token_json.get("expires_in")
        credentials.expires_at = expires_at
        credentials.scope = token_json.get("scope")

        # Update connector config
        connector.config = credentials.to_dict()
        await session.commit()
        await session.refresh(connector)

        logger.info(
            f"Successfully refreshed Airtable token for connector {connector.id}"
        )

        return connector
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to refresh Airtable token: {e!s}"
        ) from e
