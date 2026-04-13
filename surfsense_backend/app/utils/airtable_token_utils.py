"""
Airtable token refresh utilities.

This module contains shared utilities for refreshing Airtable OAuth tokens.
Extracted from routes to avoid circular imports.
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
from app.utils.oauth_security import TokenEncryption

logger = logging.getLogger(__name__)

# Airtable OAuth token endpoint
TOKEN_URL = "https://airtable.com/oauth2/v1/token"


def make_basic_auth_header(client_id: str, client_secret: str) -> str:
    """Create HTTP Basic authentication header."""
    credentials = f"{client_id}:{client_secret}".encode()
    b64 = base64.b64encode(credentials).decode("ascii")
    return f"Basic {b64}"


def get_token_encryption() -> TokenEncryption:
    """Get or create token encryption instance."""
    if not config.SECRET_KEY:
        raise ValueError("SECRET_KEY must be set for token encryption")
    return TokenEncryption(config.SECRET_KEY)


async def refresh_airtable_token(
    session: AsyncSession, connector: SearchSourceConnector
) -> SearchSourceConnector:
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

        # Decrypt tokens if they are encrypted
        token_encryption = get_token_encryption()
        is_encrypted = connector.config.get("_token_encrypted", False)

        refresh_token = credentials.refresh_token
        if is_encrypted and refresh_token:
            try:
                refresh_token = token_encryption.decrypt_token(refresh_token)
            except Exception as e:
                logger.error(f"Failed to decrypt refresh token: {e!s}")
                raise HTTPException(
                    status_code=500, detail="Failed to decrypt stored refresh token"
                ) from e

        if not refresh_token:
            raise HTTPException(
                status_code=400,
                detail="No refresh token available. Please re-authenticate.",
            )

        auth_header = make_basic_auth_header(
            config.AIRTABLE_CLIENT_ID, config.AIRTABLE_CLIENT_SECRET
        )

        # Prepare token refresh data
        refresh_data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": config.AIRTABLE_CLIENT_ID,
            "client_secret": config.AIRTABLE_CLIENT_SECRET,
        }

        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                TOKEN_URL,
                data=refresh_data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": auth_header,
                },
                timeout=30.0,
            )

        if token_response.status_code != 200:
            error_detail = token_response.text
            try:
                error_json = token_response.json()
                error_detail = error_json.get("error_description", error_detail)
            except Exception:
                pass
            raise HTTPException(
                status_code=400, detail=f"Token refresh failed: {error_detail}"
            )

        token_json = token_response.json()

        # Calculate expiration time (UTC, tz-aware)
        expires_at = None
        if token_json.get("expires_in"):
            now_utc = datetime.now(UTC)
            expires_at = now_utc + timedelta(seconds=int(token_json["expires_in"]))

        # Encrypt new tokens before storing
        access_token = token_json.get("access_token")
        new_refresh_token = token_json.get("refresh_token")

        if not access_token:
            raise HTTPException(
                status_code=400, detail="No access token received from Airtable refresh"
            )

        # Update credentials object with encrypted tokens
        credentials.access_token = token_encryption.encrypt_token(access_token)
        if new_refresh_token:
            credentials.refresh_token = token_encryption.encrypt_token(
                new_refresh_token
            )
        credentials.expires_in = token_json.get("expires_in")
        credentials.expires_at = expires_at
        credentials.scope = token_json.get("scope")

        # Update connector config with encrypted tokens
        credentials_dict = credentials.to_dict()
        credentials_dict["_token_encrypted"] = True
        connector.config = credentials_dict
        await session.commit()
        await session.refresh(connector)

        logger.info(
            f"Successfully refreshed Airtable token for connector {connector.id}"
        )

        return connector
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to refresh Airtable token: {e!s}"
        ) from e
