"""
Discord Connector

A module for interacting with Discord's HTTP API to retrieve guilds, channels, and message history.

Supports both direct bot token and OAuth-based authentication with token refresh.
"""

import asyncio
import datetime
import logging

import discord
from discord.ext import commands
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import config
from app.db import SearchSourceConnector
from app.routes.discord_add_connector_route import refresh_discord_token
from app.schemas.discord_auth_credentials import DiscordAuthCredentialsBase
from app.utils.oauth_security import TokenEncryption

logger = logging.getLogger(__name__)


class DiscordConnector(commands.Bot):
    """Class for retrieving guild, channel, and message history from Discord."""

    def __init__(
        self,
        token: str | None = None,
        session: AsyncSession | None = None,
        connector_id: int | None = None,
        credentials: DiscordAuthCredentialsBase | None = None,
    ):
        """
        Initialize the DiscordConnector with a bot token or OAuth credentials.

        Args:
            token: Discord bot token (optional, for backward compatibility)
            session: Database session for token refresh (optional)
            connector_id: Connector ID for token refresh (optional)
            credentials: Discord OAuth credentials (optional, will be loaded from DB if not provided)
        """
        intents = discord.Intents.default()
        intents.guilds = True  # Required to fetch guilds and channels
        intents.messages = True  # Required to fetch messages
        intents.message_content = True  # Required to read message content
        intents.members = True  # Required to fetch member information
        super().__init__(
            command_prefix="!", intents=intents
        )  # command_prefix is required but not strictly used here
        self._session = session
        self._connector_id = connector_id
        self._credentials = credentials
        # For backward compatibility, if token is provided directly, use it
        if token:
            self.token = token
        else:
            self.token = None
        self._bot_task = None  # Holds the async bot task
        self._is_running = False  # Flag to track if the bot is running
        self._start_called_event = (
            asyncio.Event()
        )  # Event to signal when start() is called

        # Event to confirm bot is ready
        @self.event
        async def on_ready():
            logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
            self._is_running = True

        @self.event
        async def on_connect():
            logger.debug("Bot connected to Discord gateway.")

        @self.event
        async def on_disconnect():
            logger.debug("Bot disconnected from Discord gateway.")
            self._is_running = False  # Reset flag on disconnect

        @self.event
        async def on_resumed():
            logger.debug("Bot resumed connection to Discord gateway.")

    async def _get_valid_token(self) -> str:
        """
        Get valid Discord bot token, refreshing if needed.

        Returns:
            Valid bot token

        Raises:
            ValueError: If credentials are missing or invalid
            Exception: If token refresh fails
        """
        # If we have a direct token (backward compatibility), use it
        if (
            self.token
            and self._session is None
            and self._connector_id is None
            and self._credentials is None
        ):
            # This means it was initialized with a direct token, use it
            return self.token

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
                        f"Decrypted Discord credentials for connector {self._connector_id}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to decrypt Discord credentials for connector {self._connector_id}: {e!s}"
                    )
                    raise ValueError(
                        f"Failed to decrypt Discord credentials: {e!s}"
                    ) from e

            try:
                self._credentials = DiscordAuthCredentialsBase.from_dict(config_data)
            except Exception as e:
                raise ValueError(f"Invalid Discord credentials: {e!s}") from e

        # Check if token is expired and refreshable
        if self._credentials.is_expired and self._credentials.is_refreshable:
            try:
                logger.info(
                    f"Discord token expired for connector {self._connector_id}, refreshing..."
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
                connector = await refresh_discord_token(self._session, connector)

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

                self._credentials = DiscordAuthCredentialsBase.from_dict(config_data)

                logger.info(
                    f"Successfully refreshed Discord token for connector {self._connector_id}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to refresh Discord token for connector {self._connector_id}: {e!s}"
                )
                raise Exception(
                    f"Failed to refresh Discord OAuth credentials: {e!s}"
                ) from e

        return self._credentials.bot_token

    async def start_bot(self):
        """Starts the bot to connect to Discord."""
        logger.info("Starting Discord bot...")

        # Get valid token (with auto-refresh if using OAuth)
        if not self.token:
            # Try to get token from credentials
            try:
                self.token = await self._get_valid_token()
            except ValueError as e:
                raise ValueError(
                    f"Discord bot token not set. {e!s} Please authenticate via OAuth or provide a token."
                ) from e

        try:
            if self._is_running:
                logger.warning(
                    "Bot is already running. Use close_bot() to stop it before starting again."
                )
                return

            # Signal that we're about to call start() - this allows _wait_until_ready() to proceed
            self._start_called_event.set()

            await self.start(self.token)
            logger.info("Discord bot started successfully.")
        except discord.LoginFailure:
            logger.error(
                "Failed to log in: Invalid token was provided. Please check your bot token."
            )
            self._is_running = False
            raise
        except discord.PrivilegedIntentsRequired as e:
            logger.error(
                f"Privileged Intents Required: {e}. Make sure all required intents are enabled in your bot's application page."
            )
            self._is_running = False
            raise
        except discord.ConnectionClosed as e:
            logger.error(f"Discord connection closed unexpectedly: {e}")
            self._is_running = False
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred while starting the bot: {e}")
            self._is_running = False
            raise

    async def close_bot(self):
        """Closes the bot's connection to Discord."""

        if self._is_running:
            logger.info("Closing Discord bot connection...")
            await self.close()
            logger.info("Discord bot connection closed.")
            self._is_running = False
        else:
            logger.info("Bot is not running or already disconnected.")

        # Reset the start event so the connector can be reused
        self._start_called_event.clear()

    def set_token(self, token: str) -> None:
        """
        Set the discord bot token (for backward compatibility).

        Args:
            token (str): The Discord bot token.
        """
        logger.info("Setting Discord bot token.")
        self.token = token
        logger.info(
            "Token set successfully. You can now start the bot with start_bot()."
        )

    async def _wait_until_ready(self):
        """Helper to wait until the bot is connected and ready."""
        logger.info("Waiting for the bot to be ready...")

        # Wait for start_bot() to actually call self.start()
        # This ensures we don't call wait_until_ready() before the client is initialized
        try:
            await asyncio.wait_for(self._start_called_event.wait(), timeout=30.0)
            logger.info("Bot start() has been called, now waiting for ready state...")
        except TimeoutError:
            logger.error("start_bot() did not call start() within 30 seconds")
            raise RuntimeError(
                "Discord client failed to initialize - start() was never called"
            ) from None

        try:
            await asyncio.wait_for(self.wait_until_ready(), timeout=60.0)
            logger.info("Bot is ready.")
        except TimeoutError:
            logger.error(
                "Bot did not become ready within 60 seconds. Connection may have failed."
            )
            raise
        except Exception as e:
            logger.error(
                f"An unexpected error occurred while waiting for the bot to be ready: {e}"
            )
            raise

    async def get_guilds(self) -> list[dict]:
        """
        Fetch all guilds (servers) the bot is in.

        Returns:
            list[dict]: A list of guilds with their ID, name, and member count.
            Each guild is represented as a dictionary.

        Raises:
            ValueError: If the token is not set.
        """
        await self._wait_until_ready()
        logger.info("Fetching guilds...")

        guilds_data = []
        for guild in self.guilds:
            member_count = (
                guild.member_count if guild.member_count is not None else "N/A"
            )
            guilds_data.append(
                {
                    "id": str(guild.id),
                    "name": guild.name,
                    "member_count": member_count,
                }
            )

        logger.info(f"Fetched {len(guilds_data)} guilds.")
        return guilds_data

    async def get_text_channels(self, guild_id: str) -> list[dict]:
        """
        Fetch all text channels in a guild.

        Args:
            guild_id (str): The ID of the guild to fetch channels from.

        Returns:
            list[dict]: A list of text channels with their ID, name, and type.
            Each channel is represented as a dictionary.

        Raises:
            discord.NotFound: If the guild is not found.
        """
        await self._wait_until_ready()
        logger.info(f"Fetching text channels for guild ID: {guild_id}")

        guild = self.get_guild(int(guild_id))
        if not guild:
            logger.warning(f"Guild with ID {guild_id} not found.")
            raise discord.NotFound(f"Guild with ID {guild_id} not found.")

        channels_data = []
        for channel in guild.channels:
            if isinstance(channel, discord.TextChannel):
                channels_data.append(
                    {"id": str(channel.id), "name": channel.name, "type": "text"}
                )

        logger.info(
            f"Fetched {len(channels_data)} text channels from guild {guild_id}."
        )
        return channels_data

    async def get_channel_history(
        self,
        channel_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict]:
        """
        Fetch message history from a text channel.

        Args:
            channel_id (str): The ID of the channel to fetch messages from.
            start_date (str): Optional start date in ISO format (YYYY-MM-DD).
            end_date (str): Optional end date in ISO format (YYYY-MM-DD).

        Returns:
            list[dict]: A list of messages with their ID, author ID, author name,
                        content, and creation timestamp.
            Each message is represented as a dictionary.

        Raises:
            discord.NotFound: If the channel is not found.
            discord.Forbidden: If the bot does not have permissions to read history in the channel.
        """
        await self._wait_until_ready()
        logger.info(f"Fetching message history for channel ID: {channel_id}")

        channel = self.get_channel(int(channel_id))
        if not channel:
            logger.warning(f"Channel with ID {channel_id} not found.")
            raise discord.NotFound(f"Channel with ID {channel_id} not found.")
        if not isinstance(channel, discord.TextChannel):
            logger.warning(f"Channel {channel_id} is not a text channel.")
            return []

        messages_data = []
        after = None
        before = None

        if start_date:
            try:
                start_datetime = datetime.datetime.fromisoformat(start_date).replace(
                    tzinfo=datetime.UTC
                )
                after = start_datetime
            except ValueError:
                logger.warning(f"Invalid start_date format: {start_date}. Ignoring.")

        if end_date:
            try:
                end_datetime = datetime.datetime.fromisoformat(f"{end_date}").replace(
                    tzinfo=datetime.UTC
                )
                before = end_datetime
            except ValueError:
                logger.warning(f"Invalid end_date format: {end_date}. Ignoring.")

        try:
            async for message in channel.history(
                limit=None, before=before, after=after
            ):
                messages_data.append(
                    {
                        "id": str(message.id),
                        "author_id": str(message.author.id),
                        "author_name": message.author.name,
                        "content": message.content,
                        "created_at": message.created_at.isoformat(),
                    }
                )
        except discord.Forbidden:
            logger.error(
                f"Bot does not have permissions to read message history in channel {channel_id}."
            )
            raise
        except discord.HTTPException as e:
            logger.error(f"Failed to fetch messages from channel {channel_id}: {e}")
            return []

        logger.info(f"Fetched {len(messages_data)} messages from channel {channel_id}.")
        return messages_data

    async def get_user_info(self, guild_id: str, user_id: str) -> dict | None:
        """
        Get information about a user in a guild.

        Args:
            guild_id (str): The ID of the guild.
            user_id (str): The ID of the user.

        Returns:
            dict | None: A dictionary with user information (ID, name, joined_at, roles)
                         or None if the user is not found.

        Raises:
            discord.NotFound: If the guild or user is not found.
            discord.Forbidden: If the bot does not have the GUILD_MEMBERS intent or
                               permissions to view members.
        """
        await self._wait_until_ready()
        logger.info(
            f"Fetching user info for user ID: {user_id} in guild ID: {guild_id}"
        )

        guild = self.get_guild(int(guild_id))
        if not guild:
            logger.warning(f"Guild with ID {guild_id} not found.")
            raise discord.NotFound(f"Guild with ID {guild_id} not found.")

        try:
            member = await guild.fetch_member(int(user_id))
            if member:
                roles = [role.name for role in member.roles if role.name != "@everyone"]
                logger.info(f"User {user_id} found in guild {guild_id}.")

                return {
                    "id": str(member.id),
                    "name": member.name,
                    "joined_at": member.joined_at.isoformat()
                    if member.joined_at
                    else None,
                    "roles": roles,
                }
            logger.warning(f"User {user_id} not found in guild {guild_id}.")
            return None
        except discord.NotFound:
            logger.warning(f"User {user_id} not found in guild {guild_id}.")
            return None
        except discord.Forbidden:
            logger.error(
                f"Bot does not have permissions to fetch members in guild {guild_id}. Ensure GUILD_MEMBERS intent is enabled."
            )
            raise
        except discord.HTTPException as e:
            logger.error(
                f"Failed to fetch user info for {user_id} in guild {guild_id}: {e}"
            )
            return None
