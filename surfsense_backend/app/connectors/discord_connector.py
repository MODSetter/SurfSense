"""
Discord Connector

A module for interacting with Discord's HTTP API to retrieve guilds, channels, and message history.

Requires a Discord bot token.
"""

import logging
import discord
from discord.ext import commands
import datetime

logger = logging.getLogger(__name__)


class DiscordConnector:
    """Class for retrieving guild, channel, and message history from Discord."""

    def __init__(self, token: str = None):
        """
        Initialize the DiscordConnector with a bot token.

        Args:
            token (str): The Discord bot token.
        """
        intents = discord.Intents.default()
        intents.guilds = True  # Required to fetch guilds and channels
        intents.messages = True  # Required to fetch messages
        intents.message_content = True  # Required to read message content
        intents.members = True  # Required to fetch member information
        super().__init__(command_prefix="!", intents=intents) # command_prefix is required but not strictly used here
        self.token = token
        self._ready = False

        # Event to confirm bot is ready
        @self.event
        async def on_ready():
            logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
            self._ready = True

    async def start_bot(self):
        """Starts the bot to connect to Discord."""
        if not self.token:
            raise ValueError("Discord bot token not set. Call set_token(token) first.")
        await self.start(self.token)

    async def close_bot(self):
        """Closes the bot's connection to Discord."""
        await self.close()


    def set_token(self, token: str) -> None:
        """
        Set the discord bot token.

        Args:
            token (str): The Discord bot token.
        """
        self.token = token
    
    async def _wait_until_ready(self):
        """Helper to wait until the bot is connected and ready."""
        if not self._ready:
            logger.info("Bot not yet ready, waiting...")
            await self.wait_until_ready()
            logger.info("Bot is now ready.")

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

        guilds_data = []
        for guild in self.guilds:
            member_count = guild.member_count if guild.member_count is not None else "N/A"
            guilds_data.append(
                {
                    "id": str(guild.id),
                    "name": guild.name,
                    "member_count": member_count,
                }
            )
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
        return channels_data

    async def get_channel_history(
        self,
        channel_id: str,
        limit: int = 100,
        start_date: str = None,
        end_date: str = None,
    ) -> list[dict]:
        """
        Fetch message history from a text channel.

        Args:
            channel_id (str): The ID of the channel to fetch messages from.
            limit (int): Maximum number of messages to fetch.
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
                start_datetime = datetime.datetime.fromisoformat(start_date).replace(tzinfo=datetime.timezone.utc)
                after = start_datetime
            except ValueError:
                logger.warning(f"Invalid start_date format: {start_date}. Ignoring.")

        if end_date:
            try:
                end_datetime = datetime.datetime.fromisoformat(f"{end_date}T23:59:59.999999").replace(tzinfo=datetime.timezone.utc)
                before = end_datetime
            except ValueError:
                logger.warning(f"Invalid end_date format: {end_date}. Ignoring.")

        try:
            async for message in channel.history(limit=limit, before=before, after=after):
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
            logger.error(f"Bot does not have permissions to read message history in channel {channel_id}.")
            raise
        except discord.HTTPException as e:
            logger.error(f"Failed to fetch messages from channel {channel_id}: {e}")
            return []

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

        guild = self.get_guild(int(guild_id))
        if not guild:
            logger.warning(f"Guild with ID {guild_id} not found.")
            raise discord.NotFound(f"Guild with ID {guild_id} not found.")

        try:
            member = await guild.fetch_member(int(user_id))
            if member:
                roles = [role.name for role in member.roles if role.name != "@everyone"]
                return {
                    "id": str(member.id),
                    "name": member.name,
                    "joined_at": member.joined_at.isoformat() if member.joined_at else None,
                    "roles": roles,
                }
            return None
        except discord.NotFound:
            logger.warning(f"User {user_id} not found in guild {guild_id}.")
            return None
        except discord.Forbidden:
            logger.error(f"Bot does not have permissions to fetch members in guild {guild_id}. Ensure GUILD_MEMBERS intent is enabled.")
            raise
        except discord.HTTPException as e:
            logger.error(f"Failed to fetch user info for {user_id} in guild {guild_id}: {e}")
            return None
