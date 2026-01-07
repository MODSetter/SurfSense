"""
ClickUp History Module

A module for retrieving data from ClickUp with OAuth support and backward compatibility.
Allows fetching tasks from workspaces and lists with automatic token refresh.
"""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import config
from app.connectors.clickup_connector import ClickUpConnector
from app.db import SearchSourceConnector
from app.routes.clickup_add_connector_route import refresh_clickup_token
from app.schemas.clickup_auth_credentials import ClickUpAuthCredentialsBase
from app.utils.oauth_security import TokenEncryption

logger = logging.getLogger(__name__)


class ClickUpHistoryConnector:
    """
    Class for retrieving data from ClickUp with OAuth support and backward compatibility.
    """

    def __init__(
        self,
        session: AsyncSession,
        connector_id: int,
        credentials: ClickUpAuthCredentialsBase | None = None,
        api_token: str | None = None,  # For backward compatibility
    ):
        """
        Initialize the ClickUpHistoryConnector.

        Args:
            session: Database session for token refresh
            connector_id: Connector ID for direct updates
            credentials: ClickUp OAuth credentials (optional, will be loaded from DB if not provided)
            api_token: Legacy API token for backward compatibility (optional)
        """
        self._session = session
        self._connector_id = connector_id
        self._credentials = credentials
        self._api_token = api_token  # Legacy API token
        self._use_oauth = False
        self._use_legacy = api_token is not None
        self._clickup_client: ClickUpConnector | None = None

    async def _get_valid_token(self) -> str:
        """
        Get valid ClickUp access token, refreshing if needed.
        For legacy API tokens, returns the token directly.

        Returns:
            Valid access token or API token

        Raises:
            ValueError: If credentials are missing or invalid
            Exception: If token refresh fails
        """
        # If using legacy API token, return it directly
        if self._use_legacy and self._api_token:
            return self._api_token

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

            # Check if using OAuth or legacy API token
            is_oauth = config_data.get("_token_encrypted", False) or config_data.get(
                "access_token"
            )
            has_legacy_token = config_data.get("CLICKUP_API_TOKEN") is not None

            if is_oauth:
                # OAuth 2.0 authentication
                self._use_oauth = True
                # Decrypt credentials if they are encrypted
                token_encrypted = config_data.get("_token_encrypted", False)
                if token_encrypted and config.SECRET_KEY:
                    try:
                        token_encryption = TokenEncryption(config.SECRET_KEY)

                        # Decrypt sensitive fields
                        if config_data.get("access_token"):
                            config_data["access_token"] = (
                                token_encryption.decrypt_token(
                                    config_data["access_token"]
                                )
                            )
                        if config_data.get("refresh_token"):
                            config_data["refresh_token"] = (
                                token_encryption.decrypt_token(
                                    config_data["refresh_token"]
                                )
                            )

                        logger.info(
                            f"Decrypted ClickUp OAuth credentials for connector {self._connector_id}"
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to decrypt ClickUp OAuth credentials for connector {self._connector_id}: {e!s}"
                        )
                        raise ValueError(
                            f"Failed to decrypt ClickUp OAuth credentials: {e!s}"
                        ) from e

                try:
                    self._credentials = ClickUpAuthCredentialsBase.from_dict(
                        config_data
                    )
                except Exception as e:
                    raise ValueError(f"Invalid ClickUp OAuth credentials: {e!s}") from e
            elif has_legacy_token:
                # Legacy API token authentication (backward compatibility)
                self._use_legacy = True
                self._api_token = config_data.get("CLICKUP_API_TOKEN")

                # Decrypt token if it's encrypted (legacy tokens might be encrypted)
                token_encrypted = config_data.get("_token_encrypted", False)
                if token_encrypted and config.SECRET_KEY and self._api_token:
                    try:
                        token_encryption = TokenEncryption(config.SECRET_KEY)
                        self._api_token = token_encryption.decrypt_token(
                            self._api_token
                        )
                        logger.info(
                            f"Decrypted legacy ClickUp API token for connector {self._connector_id}"
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to decrypt legacy ClickUp API token for connector {self._connector_id}: {e!s}. "
                            "Trying to use token as-is (might be unencrypted)."
                        )
                        # Continue with token as-is - might be unencrypted legacy token

                if not self._api_token:
                    raise ValueError("ClickUp API token not found in connector config")

                # Return legacy token directly (no refresh needed)
                return self._api_token
            else:
                raise ValueError(
                    "ClickUp credentials not found in connector config (neither OAuth nor API token)"
                )

        # Check if token is expired and refreshable (only for OAuth)
        if (
            self._use_oauth
            and self._credentials.is_expired
            and self._credentials.is_refreshable
        ):
            try:
                logger.info(
                    f"ClickUp token expired for connector {self._connector_id}, refreshing..."
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
                connector = await refresh_clickup_token(self._session, connector)

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

                self._credentials = ClickUpAuthCredentialsBase.from_dict(config_data)

                # Invalidate cached client so it's recreated with new token
                self._clickup_client = None

                logger.info(
                    f"Successfully refreshed ClickUp token for connector {self._connector_id}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to refresh ClickUp token for connector {self._connector_id}: {e!s}"
                )
                raise Exception(
                    f"Failed to refresh ClickUp OAuth credentials: {e!s}"
                ) from e

        if self._use_oauth:
            return self._credentials.access_token
        else:
            return self._api_token

    async def _get_client(self) -> ClickUpConnector:
        """
        Get or create ClickUpConnector with valid token.

        Returns:
            ClickUpConnector instance
        """
        if self._clickup_client is None:
            token = await self._get_valid_token()
            # ClickUp API uses Bearer token for OAuth, or direct token for legacy
            if self._use_oauth:
                # For OAuth, use Bearer token format (ClickUp OAuth expects "Bearer {token}")
                self._clickup_client = ClickUpConnector(api_token=f"Bearer {token}")
            else:
                # For legacy API token, use token directly (format: "pk_...")
                self._clickup_client = ClickUpConnector(api_token=token)
        return self._clickup_client

    async def close(self):
        """Close any open connections."""
        self._clickup_client = None

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def get_authorized_workspaces(self) -> dict[str, Any]:
        """
        Fetch authorized workspaces (teams) from ClickUp.

        Returns:
            Dictionary containing teams data

        Raises:
            ValueError: If credentials have not been set
            Exception: If the API request fails
        """
        client = await self._get_client()
        return client.get_authorized_workspaces()

    async def get_workspace_tasks(
        self, workspace_id: str, include_closed: bool = False
    ) -> list[dict[str, Any]]:
        """
        Fetch all tasks from a ClickUp workspace.

        Args:
            workspace_id: ClickUp workspace (team) ID
            include_closed: Whether to include closed tasks (default: False)

        Returns:
            List of task objects

        Raises:
            ValueError: If credentials have not been set
            Exception: If the API request fails
        """
        client = await self._get_client()
        return client.get_workspace_tasks(
            workspace_id=workspace_id, include_closed=include_closed
        )

    async def get_tasks_in_date_range(
        self,
        workspace_id: str,
        start_date: str,
        end_date: str,
        include_closed: bool = False,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        Fetch tasks from ClickUp within a specific date range.

        Args:
            workspace_id: ClickUp workspace (team) ID
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            include_closed: Whether to include closed tasks (default: False)

        Returns:
            Tuple containing (tasks list, error message or None)
        """
        client = await self._get_client()
        return client.get_tasks_in_date_range(
            workspace_id=workspace_id,
            start_date=start_date,
            end_date=end_date,
            include_closed=include_closed,
        )

    async def get_task_details(self, task_id: str) -> dict[str, Any]:
        """
        Fetch detailed information about a specific task.

        Args:
            task_id: ClickUp task ID

        Returns:
            Task details

        Raises:
            ValueError: If credentials have not been set
            Exception: If the API request fails
        """
        client = await self._get_client()
        return client.get_task_details(task_id)

    async def get_task_comments(self, task_id: str) -> dict[str, Any]:
        """
        Fetch comments for a specific task.

        Args:
            task_id: ClickUp task ID

        Returns:
            Task comments

        Raises:
            ValueError: If credentials have not been set
            Exception: If the API request fails
        """
        client = await self._get_client()
        return client.get_task_comments(task_id)
