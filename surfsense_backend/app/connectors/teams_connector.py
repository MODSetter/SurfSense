"""
Microsoft Teams Connector

A module for interacting with Microsoft Teams Graph API to retrieve teams, channels, and message history.

Supports OAuth-based authentication with token refresh.
"""

import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import config
from app.db import SearchSourceConnector
from app.routes.teams_add_connector_route import refresh_teams_token
from app.schemas.teams_auth_credentials import TeamsAuthCredentialsBase
from app.utils.oauth_security import TokenEncryption

logger = logging.getLogger(__name__)


class TeamsConnector:
    """Class for retrieving teams, channels, and message history from Microsoft Teams."""

    # Microsoft Graph API endpoints
    GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"

    def __init__(
        self,
        access_token: str | None = None,
        session: AsyncSession | None = None,
        connector_id: int | None = None,
        credentials: TeamsAuthCredentialsBase | None = None,
    ):
        """
        Initialize the TeamsConnector with an access token or OAuth credentials.

        Args:
            access_token: Microsoft Graph API access token (optional, for backward compatibility)
            session: Database session for token refresh (optional)
            connector_id: Connector ID for token refresh (optional)
            credentials: Teams OAuth credentials (optional, will be loaded from DB if not provided)
        """
        self._session = session
        self._connector_id = connector_id
        self._credentials = credentials
        self._access_token = access_token

    async def _get_valid_token(self) -> str:
        """
        Get valid Microsoft Teams access token, refreshing if needed.

        Returns:
            Valid access token

        Raises:
            ValueError: If credentials are missing or invalid
            Exception: If token refresh fails
        """
        # If we have a direct token (backward compatibility), use it
        if (
            self._access_token
            and self._session is None
            and self._connector_id is None
            and self._credentials is None
        ):
            return self._access_token

        # Load credentials from DB if not provided
        if self._credentials is None:
            if not self._session or not self._connector_id:
                raise ValueError(
                    "Cannot load credentials: session and connector_id required"
                )

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
                        "Decrypted Teams credentials for connector %s",
                        self._connector_id,
                    )
                except Exception as e:
                    logger.error(
                        "Failed to decrypt Teams credentials for connector %s: %s",
                        self._connector_id,
                        str(e),
                    )
                    raise ValueError(
                        f"Failed to decrypt Teams credentials: {e!s}"
                    ) from e

            try:
                self._credentials = TeamsAuthCredentialsBase.from_dict(config_data)
            except Exception as e:
                raise ValueError(f"Invalid Teams credentials: {e!s}") from e

        # Check if token is expired and refreshable
        if self._credentials.is_expired and self._credentials.is_refreshable:
            try:
                logger.info(
                    "Teams token expired for connector %s, refreshing...",
                    self._connector_id,
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
                connector = await refresh_teams_token(self._session, connector)

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

                self._credentials = TeamsAuthCredentialsBase.from_dict(config_data)

                logger.info(
                    "Successfully refreshed Teams token for connector %s",
                    self._connector_id,
                )
            except Exception as e:
                logger.error(
                    "Failed to refresh Teams token for connector %s: %s",
                    self._connector_id,
                    str(e),
                )
                raise ValueError(
                    f"Failed to refresh Teams OAuth credentials: {e!s}"
                ) from e

        return self._credentials.access_token

    async def get_joined_teams(self) -> list[dict[str, Any]]:
        """
        Get list of all teams the user is a member of.

        Returns:
            List of team objects with id, display_name, etc.
        """
        access_token = await self._get_valid_token()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.GRAPH_API_BASE}/me/joinedTeams",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30.0,
            )

            if response.status_code != 200:
                raise ValueError(
                    f"Failed to get joined teams: {response.status_code} - {response.text}"
                )

            data = response.json()
            return data.get("value", [])

    async def get_team_channels(self, team_id: str) -> list[dict[str, Any]]:
        """
        Get list of all channels in a team.

        Args:
            team_id: The team ID

        Returns:
            List of channel objects
        """
        access_token = await self._get_valid_token()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.GRAPH_API_BASE}/teams/{team_id}/channels",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30.0,
            )

            if response.status_code != 200:
                raise ValueError(
                    f"Failed to get channels for team {team_id}: {response.status_code} - {response.text}"
                )

            data = response.json()
            return data.get("value", [])

    async def get_channel_messages(
        self,
        team_id: str,
        channel_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get messages from a specific channel with optional date filtering.

        Args:
            team_id: The team ID
            channel_id: The channel ID
            start_date: Optional start date for filtering messages
            end_date: Optional end date for filtering messages

        Returns:
            List of message objects
        """
        access_token = await self._get_valid_token()

        async with httpx.AsyncClient() as client:
            url = (
                f"{self.GRAPH_API_BASE}/teams/{team_id}/channels/{channel_id}/messages"
            )

            # Note: The Graph API for channel messages doesn't support $filter parameter
            # We fetch all messages and filter them client-side
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30.0,
            )

            if response.status_code != 200:
                raise ValueError(
                    f"Failed to get messages from channel {channel_id}: {response.status_code} - {response.text}"
                )

            data = response.json()
            messages = data.get("value", [])

            # Filter messages by date if needed (client-side filtering)
            if start_date or end_date:
                # Make sure comparison dates are timezone-aware (UTC)
                if start_date and start_date.tzinfo is None:
                    start_date = start_date.replace(tzinfo=UTC)
                if end_date and end_date.tzinfo is None:
                    end_date = end_date.replace(tzinfo=UTC)

                filtered_messages = []
                for message in messages:
                    created_at_str = message.get("createdDateTime")
                    if not created_at_str:
                        continue

                    # Parse the ISO 8601 datetime string (already timezone-aware)
                    created_at = datetime.fromisoformat(
                        created_at_str.replace("Z", "+00:00")
                    )

                    # Check if message is within date range
                    if start_date and created_at < start_date:
                        continue
                    if end_date and created_at > end_date:
                        continue

                    filtered_messages.append(message)

                return filtered_messages

            return messages

    async def get_message_replies(
        self, team_id: str, channel_id: str, message_id: str
    ) -> list[dict[str, Any]]:
        """
        Get replies to a specific message.

        Args:
            team_id: The team ID
            channel_id: The channel ID
            message_id: The message ID

        Returns:
            List of reply message objects
        """
        access_token = await self._get_valid_token()

        async with httpx.AsyncClient() as client:
            url = f"{self.GRAPH_API_BASE}/teams/{team_id}/channels/{channel_id}/messages/{message_id}/replies"

            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30.0,
            )

            if response.status_code != 200:
                logger.warning(
                    "Failed to get replies for message %s: %s - %s",
                    message_id,
                    response.status_code,
                    response.text,
                )
                return []

            data = response.json()
            return data.get("value", [])
