"""
Jira OAuth Connector.

Handles OAuth-based authentication and token refresh for Jira API access.
Supports both OAuth 2.0 (preferred) and legacy API token authentication.
"""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import config
from app.connectors.jira_connector import JiraConnector
from app.db import SearchSourceConnector
from app.routes.jira_add_connector_route import refresh_jira_token
from app.schemas.atlassian_auth_credentials import AtlassianAuthCredentialsBase
from app.utils.oauth_security import TokenEncryption

logger = logging.getLogger(__name__)


class JiraHistoryConnector:
    """
    Jira connector with OAuth support and automatic token refresh.

    This connector uses OAuth 2.0 access tokens to authenticate with the
    Jira API. It automatically refreshes expired tokens when needed.
    Also supports legacy API token authentication for backward compatibility.
    """

    def __init__(
        self,
        session: AsyncSession,
        connector_id: int,
        credentials: AtlassianAuthCredentialsBase | None = None,
    ):
        """
        Initialize the JiraHistoryConnector with auto-refresh capability.

        Args:
            session: Database session for updating connector
            connector_id: Connector ID for direct updates
            credentials: Jira OAuth credentials (optional, will be loaded from DB if not provided)
        """
        self._session = session
        self._connector_id = connector_id
        self._credentials = credentials
        self._cloud_id: str | None = None
        self._base_url: str | None = None
        self._jira_client: JiraConnector | None = None
        self._use_oauth = True
        self._legacy_email: str | None = None
        self._legacy_api_token: str | None = None

    async def _get_valid_token(self) -> str:
        """
        Get valid Jira access token, refreshing if needed.

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

            # Check if using OAuth or legacy API token
            is_oauth = config_data.get("_token_encrypted", False) or config_data.get(
                "access_token"
            )

            if is_oauth:
                # OAuth 2.0 authentication
                if not config.SECRET_KEY:
                    raise ValueError(
                        "SECRET_KEY not configured but tokens are marked as encrypted"
                    )

                try:
                    token_encryption = TokenEncryption(config.SECRET_KEY)

                    # Decrypt access_token
                    if config_data.get("access_token"):
                        config_data["access_token"] = token_encryption.decrypt_token(
                            config_data["access_token"]
                        )
                        logger.info(
                            f"Decrypted Jira access token for connector {self._connector_id}"
                        )

                    # Decrypt refresh_token if present
                    if config_data.get("refresh_token"):
                        config_data["refresh_token"] = token_encryption.decrypt_token(
                            config_data["refresh_token"]
                        )
                        logger.info(
                            f"Decrypted Jira refresh token for connector {self._connector_id}"
                        )
                except Exception as e:
                    logger.error(
                        f"Failed to decrypt Jira credentials for connector {self._connector_id}: {e!s}"
                    )
                    raise ValueError(
                        f"Failed to decrypt Jira credentials: {e!s}"
                    ) from e

                try:
                    self._credentials = AtlassianAuthCredentialsBase.from_dict(
                        config_data
                    )
                    self._cloud_id = config_data.get("cloud_id")
                    self._base_url = config_data.get("base_url")
                    self._use_oauth = True
                except Exception as e:
                    raise ValueError(f"Invalid Jira OAuth credentials: {e!s}") from e
            else:
                # Legacy API token authentication
                self._legacy_email = config_data.get("JIRA_EMAIL")
                self._legacy_api_token = config_data.get("JIRA_API_TOKEN")
                self._base_url = config_data.get("JIRA_BASE_URL")
                self._use_oauth = False

                if (
                    not self._legacy_email
                    or not self._legacy_api_token
                    or not self._base_url
                ):
                    raise ValueError("Jira credentials not found in connector config")

        # Check if token is expired and refreshable (only for OAuth)
        if (
            self._use_oauth
            and self._credentials.is_expired
            and self._credentials.is_refreshable
        ):
            try:
                logger.info(
                    f"Jira token expired for connector {self._connector_id}, refreshing..."
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
                connector = await refresh_jira_token(self._session, connector)

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

                self._credentials = AtlassianAuthCredentialsBase.from_dict(config_data)
                self._cloud_id = config_data.get("cloud_id")
                self._base_url = config_data.get("base_url")

                # Invalidate cached client so it's recreated with new token
                self._jira_client = None

                logger.info(
                    f"Successfully refreshed Jira token for connector {self._connector_id}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to refresh Jira token for connector {self._connector_id}: {e!s}"
                )
                raise Exception(
                    f"Failed to refresh Jira OAuth credentials: {e!s}"
                ) from e

        if self._use_oauth:
            return self._credentials.access_token
        else:
            # For legacy auth, return empty string (not used for token-based auth)
            return ""

    async def _get_jira_client(self) -> JiraConnector:
        """
        Get or create JiraConnector with valid credentials.

        Returns:
            JiraConnector instance
        """
        if self._jira_client is None:
            if self._use_oauth:
                # Ensure we have valid token (will refresh if needed)
                await self._get_valid_token()

                self._jira_client = JiraConnector(
                    base_url=self._base_url,
                    access_token=self._credentials.access_token,
                    cloud_id=self._cloud_id,
                )
            else:
                # Legacy API token authentication
                self._jira_client = JiraConnector(
                    base_url=self._base_url,
                    email=self._legacy_email,
                    api_token=self._legacy_api_token,
                )
        else:
            # If OAuth, refresh token if expired before returning client
            if self._use_oauth:
                await self._get_valid_token()
                # Update client with new token if it was refreshed
                if self._credentials:
                    self._jira_client.set_oauth_credentials(
                        base_url=self._base_url or "",
                        access_token=self._credentials.access_token,
                        cloud_id=self._cloud_id,
                    )

        return self._jira_client

    async def get_issues_by_date_range(
        self,
        start_date: str,
        end_date: str,
        include_comments: bool = True,
        project_key: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        Fetch issues within a date range.
        This method wraps JiraConnector.get_issues_by_date_range() with automatic token refresh.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format (inclusive)
            include_comments: Whether to include comments in the response
            project_key: Optional project key to filter issues

        Returns:
            Tuple containing (issues list, error message or None)
        """
        # Ensure token is valid (will refresh if needed)
        if self._use_oauth:
            await self._get_valid_token()

        # Get client with valid credentials
        client = await self._get_jira_client()

        # JiraConnector methods are synchronous, so we call them directly
        # Token refresh has already been handled above
        return client.get_issues_by_date_range(
            start_date=start_date,
            end_date=end_date,
            include_comments=include_comments,
            project_key=project_key,
        )

    def format_issue(self, issue: dict[str, Any]) -> dict[str, Any]:
        """
        Format an issue for easier consumption.
        Wraps JiraConnector.format_issue().

        Args:
            issue: The issue object from Jira API

        Returns:
            Formatted issue dictionary
        """
        # This is a synchronous method that doesn't need token refresh
        # since it just formats data that's already been fetched
        if self._jira_client is None:
            # Create a minimal client just for formatting (doesn't need credentials)
            self._jira_client = JiraConnector()
        return self._jira_client.format_issue(issue)

    def format_issue_to_markdown(self, issue: dict[str, Any]) -> str:
        """
        Convert an issue to markdown format.
        Wraps JiraConnector.format_issue_to_markdown().

        Args:
            issue: The issue object (either raw or formatted)

        Returns:
            Markdown string representation of the issue
        """
        # This is a synchronous method that doesn't need token refresh
        # since it just formats data that's already been fetched
        if self._jira_client is None:
            # Create a minimal client just for formatting (doesn't need credentials)
            self._jira_client = JiraConnector()
        return self._jira_client.format_issue_to_markdown(issue)

    async def close(self):
        """Close any resources (currently no-op for JiraConnector)."""
        # JiraConnector doesn't maintain persistent connections, so nothing to close
        self._jira_client = None

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
