"""
Airtable OAuth Connector.

Handles OAuth-based authentication and token refresh for Airtable API access.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import config
from app.connectors.airtable_connector import AirtableConnector
from app.db import SearchSourceConnector
from app.routes.airtable_add_connector_route import refresh_airtable_token
from app.schemas.airtable_auth_credentials import AirtableAuthCredentialsBase
from app.utils.oauth_security import TokenEncryption

logger = logging.getLogger(__name__)


class AirtableHistoryConnector:
    """
    Airtable connector with OAuth support and automatic token refresh.

    This connector uses OAuth 2.0 access tokens to authenticate with the
    Airtable API. It automatically refreshes expired tokens when needed.
    """

    def __init__(
        self,
        session: AsyncSession,
        connector_id: int,
        credentials: AirtableAuthCredentialsBase | None = None,
    ):
        """
        Initialize the AirtableHistoryConnector with auto-refresh capability.

        Args:
            session: Database session for updating connector
            connector_id: Connector ID for direct updates
            credentials: Airtable OAuth credentials (optional, will be loaded from DB if not provided)
        """
        self._session = session
        self._connector_id = connector_id
        self._credentials = credentials
        self._airtable_connector: AirtableConnector | None = None

    async def _get_valid_token(self) -> str:
        """
        Get valid Airtable access token, refreshing if needed.

        Returns:
            Valid access token

        Raises:
            ValueError: If credentials are missing or invalid
            Exception: If token refresh fails
        """
        # Load credentials from DB if not provided
        if self._credentials is None:
            result = await self._session.execute(
                select(SearchSourceConnector).filter(
                    SearchSourceConnector.id == self._connector_id
                )
            )
            connector = result.scalars().first()

            if not connector:
                raise ValueError(f"Connector {self._connector_id} not found")

            config_data = connector.config.copy()

            # Decrypt credentials if they are encrypted
            token_encrypted = config_data.get("_token_encrypted", False)
            if token_encrypted and config.SECRET_KEY:
                try:
                    token_encryption = TokenEncryption(config.SECRET_KEY)

                    # Decrypt sensitive fields
                    if config_data.get("access_token"):
                        config_data["access_token"] = token_encryption.decrypt_token(
                            config_data["access_token"]
                        )
                    if config_data.get("refresh_token"):
                        config_data["refresh_token"] = token_encryption.decrypt_token(
                            config_data["refresh_token"]
                        )

                    logger.info(
                        f"Decrypted Airtable credentials for connector {self._connector_id}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to decrypt Airtable credentials for connector {self._connector_id}: {e!s}"
                    )
                    raise ValueError(
                        f"Failed to decrypt Airtable credentials: {e!s}"
                    ) from e

            try:
                self._credentials = AirtableAuthCredentialsBase.from_dict(config_data)
            except Exception as e:
                raise ValueError(f"Invalid Airtable credentials: {e!s}") from e

        # Check if token is expired and refreshable
        if self._credentials.is_expired and self._credentials.is_refreshable:
            try:
                logger.info(
                    f"Airtable token expired for connector {self._connector_id}, refreshing..."
                )

                # Get connector for refresh
                result = await self._session.execute(
                    select(SearchSourceConnector).filter(
                        SearchSourceConnector.id == self._connector_id
                    )
                )
                connector = result.scalars().first()

                if not connector:
                    raise RuntimeError(
                        f"Connector {self._connector_id} not found; cannot refresh token."
                    )

                # Refresh token
                connector = await refresh_airtable_token(self._session, connector)

                # Reload credentials after refresh
                config_data = connector.config.copy()
                token_encrypted = config_data.get("_token_encrypted", False)
                if token_encrypted and config.SECRET_KEY:
                    token_encryption = TokenEncryption(config.SECRET_KEY)
                    if config_data.get("access_token"):
                        config_data["access_token"] = token_encryption.decrypt_token(
                            config_data["access_token"]
                        )
                    if config_data.get("refresh_token"):
                        config_data["refresh_token"] = token_encryption.decrypt_token(
                            config_data["refresh_token"]
                        )

                self._credentials = AirtableAuthCredentialsBase.from_dict(config_data)

                # Invalidate cached connector so it's recreated with new token
                self._airtable_connector = None

                logger.info(
                    f"Successfully refreshed Airtable token for connector {self._connector_id}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to refresh Airtable token for connector {self._connector_id}: {e!s}"
                )
                raise Exception(
                    f"Failed to refresh Airtable OAuth credentials: {e!s}"
                ) from e

        return self._credentials.access_token

    async def _get_connector(self) -> AirtableConnector:
        """
        Get or create AirtableConnector with valid token.

        Returns:
            AirtableConnector instance
        """
        if self._airtable_connector is None:
            # Ensure we have valid credentials (this will refresh if needed)
            await self._get_valid_token()
            # Use the credentials object which is now guaranteed to be valid
            if not self._credentials:
                raise ValueError("Credentials not loaded")
            self._airtable_connector = AirtableConnector(self._credentials)
        return self._airtable_connector
