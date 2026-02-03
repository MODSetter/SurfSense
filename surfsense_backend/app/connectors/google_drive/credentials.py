"""Google Drive OAuth credential management."""

import json
import logging
from datetime import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm.attributes import flag_modified

from app.config import config
from app.db import SearchSourceConnector
from app.utils.oauth_security import TokenEncryption

logger = logging.getLogger(__name__)


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

    config_data = (
        connector.config.copy()
    )  # Work with a copy to avoid modifying original

    # Decrypt credentials if they are encrypted
    token_encrypted = config_data.get("_token_encrypted", False)
    if token_encrypted and config.SECRET_KEY:
        try:
            token_encryption = TokenEncryption(config.SECRET_KEY)

            # Decrypt sensitive fields
            if config_data.get("token"):
                config_data["token"] = token_encryption.decrypt_token(
                    config_data["token"]
                )
            if config_data.get("refresh_token"):
                config_data["refresh_token"] = token_encryption.decrypt_token(
                    config_data["refresh_token"]
                )
            if config_data.get("client_secret"):
                config_data["client_secret"] = token_encryption.decrypt_token(
                    config_data["client_secret"]
                )

            logger.info(
                f"Decrypted Google Drive credentials for connector {connector_id}"
            )
        except Exception as e:
            logger.error(
                f"Failed to decrypt Google Drive credentials for connector {connector_id}: {e!s}"
            )
            raise ValueError(
                f"Failed to decrypt Google Drive credentials: {e!s}"
            ) from e

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

            creds_dict = json.loads(credentials.to_json())

            # Encrypt sensitive credentials before storing
            token_encrypted = connector.config.get("_token_encrypted", False)

            if token_encrypted and config.SECRET_KEY:
                token_encryption = TokenEncryption(config.SECRET_KEY)
                # Encrypt sensitive fields
                if creds_dict.get("token"):
                    creds_dict["token"] = token_encryption.encrypt_token(
                        creds_dict["token"]
                    )
                if creds_dict.get("refresh_token"):
                    creds_dict["refresh_token"] = token_encryption.encrypt_token(
                        creds_dict["refresh_token"]
                    )
                if creds_dict.get("client_secret"):
                    creds_dict["client_secret"] = token_encryption.encrypt_token(
                        creds_dict["client_secret"]
                    )
                creds_dict["_token_encrypted"] = True

            # IMPORTANT: Merge new credentials with existing config to preserve
            # user settings like selected_folders, selected_files, indexing_options,
            # folder_tokens, etc. that would otherwise be wiped on token refresh.
            existing_config = connector.config.copy() if connector.config else {}
            existing_config.update(creds_dict)
            connector.config = existing_config
            flag_modified(connector, "config")
            await session.commit()

        except Exception as e:
            error_str = str(e)
            # Check if this is an invalid_grant error (token expired/revoked)
            if (
                "invalid_grant" in error_str.lower()
                or "token has been expired or revoked" in error_str.lower()
            ):
                raise Exception(
                    "Google Drive authentication failed. Please re-authenticate."
                ) from e
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
