"""
Microsoft Teams History Module

A module for retrieving conversation history from Microsoft Teams channels.
Allows fetching team lists, channel lists, and message history with date range filtering.
"""

import logging
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.teams_connector import TeamsConnector
from app.schemas.teams_auth_credentials import TeamsAuthCredentialsBase

logger = logging.getLogger(__name__)


class TeamsHistory:
    """Class for retrieving conversation history from Microsoft Teams channels."""

    def __init__(
        self,
        access_token: str | None = None,
        session: AsyncSession | None = None,
        connector_id: int | None = None,
        credentials: TeamsAuthCredentialsBase | None = None,
    ):
        """
        Initialize the TeamsHistory class.

        Args:
            access_token: Microsoft Graph API access token (optional, for backward compatibility)
            session: Database session for token refresh (optional)
            connector_id: Connector ID for token refresh (optional)
            credentials: Teams OAuth credentials (optional, will be loaded from DB if not provided)
        """
        self.connector = TeamsConnector(
            access_token=access_token,
            session=session,
            connector_id=connector_id,
            credentials=credentials,
        )

    async def get_all_teams(self) -> list[dict[str, Any]]:
        """
        Get list of all teams the user has access to.

        Returns:
            List of team objects containing team metadata.
        """
        try:
            teams = await self.connector.get_joined_teams()
            logger.info("Retrieved %s teams", len(teams))
            return teams
        except Exception as e:
            logger.error("Error fetching teams: %s", str(e))
            raise

    async def get_channels_for_team(self, team_id: str) -> list[dict[str, Any]]:
        """
        Get list of all channels in a specific team.

        Args:
            team_id: The ID of the team

        Returns:
            List of channel objects containing channel metadata.
        """
        try:
            channels = await self.connector.get_team_channels(team_id)
            logger.info("Retrieved %s channels for team %s", len(channels), team_id)
            return channels
        except Exception as e:
            logger.error("Error fetching channels for team %s: %s", team_id, str(e))
            raise

    async def get_messages_from_channel(
        self,
        team_id: str,
        channel_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        include_replies: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Get messages from a specific channel with optional date filtering.

        Args:
            team_id: The ID of the team
            channel_id: The ID of the channel
            start_date: Optional start date for filtering messages
            end_date: Optional end date for filtering messages
            include_replies: Whether to include reply messages (default: True)

        Returns:
            List of message objects with content and metadata.
        """
        try:
            messages = await self.connector.get_channel_messages(
                team_id, channel_id, start_date, end_date
            )

            logger.info(
                "Retrieved %s messages from channel %s in team %s",
                len(messages),
                channel_id,
                team_id,
            )

            # Fetch replies if requested
            if include_replies:
                all_messages = []
                for message in messages:
                    all_messages.append(message)
                    # Get replies for this message
                    try:
                        replies = await self.connector.get_message_replies(
                            team_id, channel_id, message.get("id")
                        )
                        all_messages.extend(replies)
                    except Exception:
                        logger.warning(
                            "Failed to get replies for message %s",
                            message.get("id"),
                            exc_info=True,
                        )
                        # Continue without replies for this message

                logger.info(
                    "Total messages including replies: %s for channel %s",
                    len(all_messages),
                    channel_id,
                )
                return all_messages

            return messages

        except Exception as e:
            logger.error(
                "Error fetching messages from channel %s in team %s: %s",
                channel_id,
                team_id,
                str(e),
            )
            raise

    async def get_all_messages_from_team(
        self,
        team_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        include_replies: bool = True,
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Get all messages from all channels in a team.

        Args:
            team_id: The ID of the team
            start_date: Optional start date for filtering messages
            end_date: Optional end date for filtering messages
            include_replies: Whether to include reply messages (default: True)

        Returns:
            Dictionary mapping channel IDs to lists of messages.
        """
        try:
            channels = await self.get_channels_for_team(team_id)
            all_channel_messages = {}

            for channel in channels:
                channel_id = channel.get("id")
                channel_name = channel.get("displayName", "Unknown")

                try:
                    messages = await self.get_messages_from_channel(
                        team_id, channel_id, start_date, end_date, include_replies
                    )
                    all_channel_messages[channel_id] = messages
                    logger.info(
                        "Fetched %s messages from channel '%s' (%s)",
                        len(messages),
                        channel_name,
                        channel_id,
                    )
                except Exception:
                    logger.error(
                        "Failed to fetch messages from channel '%s' (%s)",
                        channel_name,
                        channel_id,
                        exc_info=True,
                    )
                    all_channel_messages[channel_id] = []

            return all_channel_messages

        except Exception as e:
            logger.error("Error fetching messages from team %s: %s", team_id, str(e))
            raise

    async def get_all_messages(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        include_replies: bool = True,
    ) -> dict[str, dict[str, list[dict[str, Any]]]]:
        """
        Get all messages from all teams and channels the user has access to.

        Args:
            start_date: Optional start date for filtering messages
            end_date: Optional end date for filtering messages
            include_replies: Whether to include reply messages (default: True)

        Returns:
            Nested dictionary: team_id -> channel_id -> list of messages.
        """
        try:
            teams = await self.get_all_teams()
            all_messages = {}

            for team in teams:
                team_id = team.get("id")
                team_name = team.get("displayName", "Unknown")

                try:
                    team_messages = await self.get_all_messages_from_team(
                        team_id, start_date, end_date, include_replies
                    )
                    all_messages[team_id] = team_messages
                    total_messages = sum(
                        len(messages) for messages in team_messages.values()
                    )
                    logger.info(
                        "Fetched %s total messages from team '%s' (%s)",
                        total_messages,
                        team_name,
                        team_id,
                    )
                except Exception:
                    logger.error(
                        "Failed to fetch messages from team '%s' (%s)",
                        team_name,
                        team_id,
                        exc_info=True,
                    )
                    all_messages[team_id] = {}

            return all_messages

        except Exception as e:
            logger.error("Error fetching all messages: %s", str(e))
            raise
