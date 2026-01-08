"""
Slack History Module

A module for retrieving conversation history from Slack channels.
Allows fetching channel lists and message history with date range filtering.
"""

import logging  # Added import
import time  # Added import
from datetime import datetime
from typing import Any

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import config
from app.db import SearchSourceConnector
from app.routes.slack_add_connector_route import refresh_slack_token
from app.schemas.slack_auth_credentials import SlackAuthCredentialsBase
from app.utils.oauth_security import TokenEncryption

logger = logging.getLogger(__name__)  # Added logger


class SlackHistory:
    """Class for retrieving conversation history from Slack channels."""

    def __init__(
        self,
        token: str | None = None,
        session: AsyncSession | None = None,
        connector_id: int | None = None,
        credentials: SlackAuthCredentialsBase | None = None,
    ):
        """
        Initialize the SlackHistory class.

        Args:
            token: Slack API token (optional, for backward compatibility)
            session: Database session for token refresh (optional)
            connector_id: Connector ID for token refresh (optional)
            credentials: Slack OAuth credentials (optional, will be loaded from DB if not provided)
        """
        self._session = session
        self._connector_id = connector_id
        self._credentials = credentials
        # For backward compatibility, if token is provided directly, use it
        if token:
            self.client = WebClient(token=token)
        else:
            self.client = None

    async def _get_valid_token(self) -> str:
        """
        Get valid Slack bot token, refreshing if needed.

        Returns:
            Valid bot token

        Raises:
            ValueError: If credentials are missing or invalid
            Exception: If token refresh fails
        """
        # If we have a direct token (backward compatibility), use it
        # Check if client was initialized with a token directly (not via credentials)
        if (
            self.client
            and self._session is None
            and self._connector_id is None
            and self._credentials is None
        ):
            # This means it was initialized with a direct token, extract it
            # WebClient stores token internally, we need to get it from the client
            # For backward compatibility, we'll use the client directly
            # But we can't easily extract the token, so we'll just use the client
            # In this case, we'll skip refresh logic
            # This is the old pattern - just use the client as-is
            # We can't extract token easily, so we'll raise an error
            # asking to use the new pattern
            raise ValueError(
                "Cannot refresh token: Please use session and connector_id for auto-refresh support"
            )

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
                    if config_data.get("bot_token"):
                        config_data["bot_token"] = token_encryption.decrypt_token(
                            config_data["bot_token"]
                        )
                    if config_data.get("refresh_token"):
                        config_data["refresh_token"] = token_encryption.decrypt_token(
                            config_data["refresh_token"]
                        )

                    logger.info(
                        f"Decrypted Slack credentials for connector {self._connector_id}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to decrypt Slack credentials for connector {self._connector_id}: {e!s}"
                    )
                    raise ValueError(
                        f"Failed to decrypt Slack credentials: {e!s}"
                    ) from e

            try:
                self._credentials = SlackAuthCredentialsBase.from_dict(config_data)
            except Exception as e:
                raise ValueError(f"Invalid Slack credentials: {e!s}") from e

        # Check if token is expired and refreshable
        if self._credentials.is_expired and self._credentials.is_refreshable:
            try:
                logger.info(
                    f"Slack token expired for connector {self._connector_id}, refreshing..."
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
                connector = await refresh_slack_token(self._session, connector)

                # Reload credentials after refresh
                config_data = connector.config.copy()
                token_encrypted = config_data.get("_token_encrypted", False)
                if token_encrypted and config.SECRET_KEY:
                    token_encryption = TokenEncryption(config.SECRET_KEY)
                    if config_data.get("bot_token"):
                        config_data["bot_token"] = token_encryption.decrypt_token(
                            config_data["bot_token"]
                        )
                    if config_data.get("refresh_token"):
                        config_data["refresh_token"] = token_encryption.decrypt_token(
                            config_data["refresh_token"]
                        )

                self._credentials = SlackAuthCredentialsBase.from_dict(config_data)

                # Invalidate cached client so it's recreated with new token
                self.client = None

                logger.info(
                    f"Successfully refreshed Slack token for connector {self._connector_id}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to refresh Slack token for connector {self._connector_id}: {e!s}"
                )
                raise Exception(
                    f"Failed to refresh Slack OAuth credentials: {e!s}"
                ) from e

        return self._credentials.bot_token

    async def _ensure_client(self) -> WebClient:
        """
        Ensure Slack client is initialized with valid token.

        Returns:
            WebClient instance
        """
        # If client was initialized with direct token (backward compatibility), use it
        if self.client and (self._session is None or self._connector_id is None):
            return self.client

        # Otherwise, initialize with token from credentials (with auto-refresh)
        if self.client is None:
            token = await self._get_valid_token()
            # Skip if it's the placeholder for direct token initialization
            if token != "direct_token_initialized":
                self.client = WebClient(token=token)
        return self.client

    def set_token(self, token: str) -> None:
        """
        Set the Slack API token (for backward compatibility).

        Args:
            token: Slack API token
        """
        self.client = WebClient(token=token)

    async def get_all_channels(
        self, include_private: bool = True
    ) -> list[dict[str, Any]]:
        """
        Fetch all channels that the bot has access to, with rate limit handling.

        Args:
            include_private: Whether to include private channels

        Returns:
            List of dictionaries, each representing a channel with id, name, is_private, is_member.

        Raises:
            ValueError: If no Slack client has been initialized
            SlackApiError: If there's an unrecoverable error calling the Slack API
            RuntimeError: For unexpected errors during channel fetching.
        """
        client = await self._ensure_client()

        channels_list = []  # Changed from dict to list
        types = "public_channel"
        if include_private:
            types += ",private_channel"

        next_cursor = None
        is_first_request = True

        while is_first_request or next_cursor:
            try:
                if not is_first_request:  # Add delay only for paginated requests
                    logger.info(
                        f"Paginating for channels, waiting 3 seconds before next call. Cursor: {next_cursor}"
                    )
                    time.sleep(3)

                current_limit = 1000  # Max limit
                api_result = client.conversations_list(
                    types=types, cursor=next_cursor, limit=current_limit
                )

                channels_on_page = api_result["channels"]
                for channel in channels_on_page:
                    if "name" in channel and "id" in channel:
                        channel_data = {
                            "id": channel.get("id"),
                            "name": channel.get("name"),
                            "is_private": channel.get("is_private", False),
                            # is_member is often part of the channel object from conversations.list
                            # It indicates if the authenticated user (bot) is a member.
                            # For public channels, this might be true or the API might not focus on it
                            # if the bot can read it anyway. For private, it's crucial.
                            "is_member": channel.get("is_member", False),
                        }
                        channels_list.append(channel_data)
                    else:
                        logger.warning(
                            f"Channel found with missing name or id. Data: {channel}"
                        )

                next_cursor = api_result.get("response_metadata", {}).get("next_cursor")
                is_first_request = False  # Subsequent requests are not the first

                if not next_cursor:  # All pages processed
                    break

            except SlackApiError as e:
                if e.response is not None and e.response.status_code == 429:
                    retry_after_header = e.response.headers.get("Retry-After")
                    wait_duration = 60  # Default wait time
                    if retry_after_header and retry_after_header.isdigit():
                        wait_duration = int(retry_after_header)

                    logger.warning(
                        f"Slack API rate limit hit while fetching channels. Waiting for {wait_duration} seconds. Cursor: {next_cursor}"
                    )
                    time.sleep(wait_duration)
                    # The loop will continue, retrying with the same cursor
                else:
                    # Not a 429 error, or no response object, re-raise
                    raise SlackApiError(
                        f"Error retrieving channels: {e}", e.response
                    ) from e
            except Exception as general_error:
                # Handle other potential errors like network issues if necessary, or re-raise
                logger.error(
                    f"An unexpected error occurred during channel fetching: {general_error}"
                )
                raise RuntimeError(
                    f"An unexpected error occurred during channel fetching: {general_error}"
                ) from general_error

        return channels_list

    async def get_conversation_history(
        self,
        channel_id: str,
        limit: int = 1000,
        oldest: int | None = None,
        latest: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Fetch conversation history for a channel.

        Args:
            channel_id: The ID of the channel to fetch history for
            limit: Maximum number of messages to return per request (default 1000)
            oldest: Start of time range (Unix timestamp)
            latest: End of time range (Unix timestamp)

        Returns:
            List of message objects

        Raises:
            ValueError: If no Slack client has been initialized
            SlackApiError: If there's an error calling the Slack API
        """
        client = await self._ensure_client()

        messages = []
        next_cursor = None

        while True:
            try:
                # Proactive delay for conversations.history (Tier 3)
                time.sleep(1.2)  # Wait 1.2 seconds before each history call.

                kwargs = {
                    "channel": channel_id,
                    "limit": min(limit, 1000),  # API max is 1000
                }
                if oldest:
                    kwargs["oldest"] = oldest
                if latest:
                    kwargs["latest"] = latest
                if next_cursor:
                    kwargs["cursor"] = next_cursor

                current_api_call_successful = False
                result = None  # Ensure result is defined
                try:
                    result = client.conversations_history(**kwargs)
                    current_api_call_successful = True
                except SlackApiError as e_history:
                    if (
                        e_history.response is not None
                        and e_history.response.status_code == 429
                    ):
                        retry_after_str = e_history.response.headers.get("Retry-After")
                        wait_time = 60  # Default
                        if retry_after_str and retry_after_str.isdigit():
                            wait_time = int(retry_after_str)
                        logger.warning(
                            f"Rate limited by Slack on conversations.history for channel {channel_id}. "
                            f"Retrying after {wait_time} seconds. Cursor: {next_cursor}"
                        )
                        time.sleep(wait_time)
                        # current_api_call_successful remains False, loop will retry this page
                    else:
                        raise  # Re-raise to outer handler for not_in_channel or other SlackApiErrors

                if not current_api_call_successful or result is None:
                    continue  # Retry the current page fetch due to handled rate limit

                # Process result if successful
                batch = result["messages"]
                messages.extend(batch)

                if result.get("has_more", False) and len(messages) < limit:
                    next_cursor = result["response_metadata"]["next_cursor"]
                else:
                    break  # Exit pagination loop

            except SlackApiError as e:  # Outer catch for not_in_channel or unhandled SlackApiErrors from inner try
                if (
                    e.response is not None
                    and hasattr(e.response, "data")
                    and isinstance(e.response.data, dict)
                    and e.response.data.get("error") == "not_in_channel"
                ):
                    logger.warning(
                        f"Bot is not in channel '{channel_id}'. Cannot fetch history. "
                        "Please add the bot to this channel."
                    )
                    return []
                # For other SlackApiErrors from inner block or this level
                raise SlackApiError(
                    f"Error retrieving history for channel {channel_id}: {e}",
                    e.response,
                ) from e
            except Exception as general_error:  # Catch any other unexpected errors
                logger.error(
                    f"Unexpected error in get_conversation_history for channel {channel_id}: {general_error}"
                )
                # Re-raise the general error to allow higher-level handling or visibility
                raise general_error from general_error

        return messages[:limit]

    @staticmethod
    def convert_date_to_timestamp(date_str: str) -> int | None:
        """
        Convert a date string in format YYYY-MM-DD to Unix timestamp.

        Args:
            date_str: Date string in YYYY-MM-DD format

        Returns:
            Unix timestamp (seconds since epoch) or None if invalid format
        """
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return int(dt.timestamp())
        except ValueError:
            return None

    async def get_history_by_date_range(
        self, channel_id: str, start_date: str, end_date: str, limit: int = 1000
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        Fetch conversation history within a date range.

        Args:
            channel_id: The ID of the channel to fetch history for
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format (inclusive)
            limit: Maximum number of messages to return

        Returns:
            Tuple containing (messages list, error message or None)
        """
        oldest = self.convert_date_to_timestamp(start_date)
        if not oldest:
            return (
                [],
                f"Invalid start date format: {start_date}. Please use YYYY-MM-DD.",
            )

        latest = self.convert_date_to_timestamp(end_date)
        if not latest:
            return [], f"Invalid end date format: {end_date}. Please use YYYY-MM-DD."

        # Add one day to end date to make it inclusive
        latest += 86400  # seconds in a day

        try:
            messages = await self.get_conversation_history(
                channel_id=channel_id, limit=limit, oldest=oldest, latest=latest
            )
            return messages, None
        except SlackApiError as e:
            return [], f"Slack API error: {e!s}"
        except ValueError as e:
            return [], str(e)

    async def get_user_info(self, user_id: str) -> dict[str, Any]:
        """
        Get information about a user.

        Args:
            user_id: The ID of the user to get info for

        Returns:
            User information dictionary

        Raises:
            ValueError: If no Slack client has been initialized
            SlackApiError: If there's an error calling the Slack API
        """
        client = await self._ensure_client()

        while True:
            try:
                # Proactive delay for users.info (Tier 4) - generally not needed unless called extremely rapidly.
                # For now, we are only adding Retry-After as per plan.
                # time.sleep(0.6) # Optional: ~100 req/min if ever needed.

                result = client.users_info(user=user_id)
                return result["user"]  # Success, return and exit loop implicitly

            except SlackApiError as e_user_info:
                if (
                    e_user_info.response is not None
                    and e_user_info.response.status_code == 429
                ):
                    retry_after_str = e_user_info.response.headers.get("Retry-After")
                    wait_time = 30  # Default for Tier 4, can be adjusted
                    if retry_after_str and retry_after_str.isdigit():
                        wait_time = int(retry_after_str)
                    logger.warning(
                        f"Rate limited by Slack on users.info for user {user_id}. Retrying after {wait_time} seconds."
                    )
                    time.sleep(wait_time)
                    continue  # Retry the API call
                else:
                    # Not a 429 error, or no response object, re-raise
                    raise SlackApiError(
                        f"Error retrieving user info for {user_id}: {e_user_info}",
                        e_user_info.response,
                    ) from e_user_info
            except Exception as general_error:  # Catch any other unexpected errors
                logger.error(
                    f"Unexpected error in get_user_info for user {user_id}: {general_error}"
                )
                raise general_error from general_error  # Re-raise unexpected errors

    async def format_message(
        self, msg: dict[str, Any], include_user_info: bool = False
    ) -> dict[str, Any]:
        """
        Format a message for easier consumption.

        Args:
            msg: The message object from Slack API
            include_user_info: Whether to fetch and include user info

        Returns:
            Formatted message dictionary
        """
        formatted = {
            "text": msg.get("text", ""),
            "timestamp": msg.get("ts"),
            "datetime": datetime.fromtimestamp(float(msg.get("ts", 0))).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "user_id": msg.get("user", "UNKNOWN"),
            "has_attachments": bool(msg.get("attachments")),
            "has_files": bool(msg.get("files")),
            "thread_ts": msg.get("thread_ts"),
            "is_thread": "thread_ts" in msg,
        }

        if include_user_info and "user" in msg:
            try:
                user_info = await self.get_user_info(msg["user"])
                formatted["user_name"] = user_info.get("real_name", "Unknown")
                formatted["user_email"] = user_info.get("profile", {}).get("email", "")
            except Exception:
                # If we can't get user info, just continue without it
                formatted["user_name"] = "Unknown"

        return formatted
