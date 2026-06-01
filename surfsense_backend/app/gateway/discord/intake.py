"""FastAPI lifespan supervisor for Discord Gateway WebSocket intake."""

from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import suppress
from typing import Any

import discord

from app.config import config
from app.db import ExternalChatPlatform, async_session_maker
from app.gateway.accounts import get_discord_account_by_guild
from app.gateway.inbox import discord_message_dedupe_key, persist_inbound_event
from app.observability.metrics import record_gateway_inbox_write

logger = logging.getLogger(__name__)

_task: asyncio.Task[None] | None = None
_client: discord.Client | None = None
_shutdown_event: asyncio.Event | None = None


def _message_reference_payload(message: discord.Message) -> dict[str, Any] | None:
    if message.reference is None:
        return None
    return {
        "message_id": str(message.reference.message_id)
        if message.reference.message_id
        else None,
        "channel_id": str(message.reference.channel_id)
        if message.reference.channel_id
        else None,
        "guild_id": str(message.reference.guild_id)
        if message.reference.guild_id
        else None,
    }


def _serialize_message(message: discord.Message, *, bot_user_id: str | None) -> dict[str, Any]:
    guild = message.guild
    channel = message.channel
    thread_id = str(channel.id) if isinstance(channel, discord.Thread) else None
    parent_id = str(channel.parent_id) if isinstance(channel, discord.Thread) else None
    return {
        "type": "message",
        "bot_user_id": bot_user_id,
        "event": {
            "type": "message",
            "id": str(message.id),
            "guild_id": str(guild.id) if guild else None,
            "guild_name": guild.name if guild else None,
            "channel_id": parent_id or str(message.channel.id),
            "thread_id": thread_id,
            "channel_name": getattr(channel, "name", None),
            "content": message.content,
            "author": {
                "id": str(message.author.id),
                "username": message.author.name,
                "bot": message.author.bot,
            },
            "mentions": [
                {"id": str(user.id), "username": user.name}
                for user in message.mentions
            ],
            "message_reference": _message_reference_payload(message),
            "created_at": message.created_at.isoformat()
            if message.created_at
            else None,
        },
    }


async def _persist_message(message: discord.Message, *, bot_user_id: str | None) -> None:
    if message.guild is None:
        return
    guild_id = str(message.guild.id)
    raw_payload = _serialize_message(message, bot_user_id=bot_user_id)

    async with async_session_maker() as session:
        account = await get_discord_account_by_guild(session, guild_id=guild_id)
        if account is None:
            logger.info("Ignoring Discord message for uninstalled guild_id=%s", guild_id)
            return

        inbox_id = await persist_inbound_event(
            session,
            account_id=account.id,
            platform=ExternalChatPlatform.DISCORD,
            event_dedupe_key=discord_message_dedupe_key(message.id),
            external_event_id=str(message.id),
            external_message_id=str(message.id),
            event_kind="message",
            raw_payload=raw_payload,
            request_id=f"gateway_{uuid.uuid4().hex[:16]}",
        )
        await session.commit()
        record_gateway_inbox_write(platform="discord", dedup_skipped=inbox_id is None)
        logger.info(
            "Persisted Discord gateway message_id=%s guild_id=%s inbox_id=%s",
            message.id,
            guild_id,
            inbox_id,
        )


def _build_client() -> discord.Client:
    intents = discord.Intents.default()
    intents.guilds = True
    intents.messages = True
    intents.message_content = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready() -> None:
        logger.info(
            "Discord gateway connected as %s (%s)",
            client.user,
            getattr(client.user, "id", None),
        )

    @client.event
    async def on_message(message: discord.Message) -> None:
        if message.author.bot:
            return
        bot_user = client.user
        if bot_user is None:
            return
        if message.author.id == bot_user.id:
            return
        bot_user_id = str(bot_user.id)
        mention_ids = {str(user.id) for user in message.mentions}
        if bot_user_id not in mention_ids:
            return
        logger.info(
            "Received Discord gateway mention message_id=%s guild_id=%s channel_id=%s content_present=%s",
            message.id,
            getattr(message.guild, "id", None),
            getattr(message.channel, "id", None),
            bool(message.content),
        )
        try:
            await _persist_message(message, bot_user_id=bot_user_id)
        except Exception:
            logger.exception("Discord gateway failed to persist message_id=%s", message.id)

    return client


async def _run_discord_gateway() -> None:
    global _client
    token = config.DISCORD_BOT_TOKEN
    if not token:
        logger.warning("Discord gateway enabled but DISCORD_BOT_TOKEN is not set")
        return

    while _shutdown_event is None or not _shutdown_event.is_set():
        _client = _build_client()
        try:
            await _client.start(token)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Discord gateway WebSocket failed; retrying in 30s")
        finally:
            if _client is not None and not _client.is_closed():
                await _client.close()
        if _shutdown_event is not None and _shutdown_event.is_set():
            break
        try:
            await asyncio.wait_for(_shutdown_event.wait(), timeout=30.0)
        except (TimeoutError, AttributeError):
            continue


async def start_discord_gateway_supervisor() -> None:
    global _shutdown_event, _task
    if not config.GATEWAY_DISCORD_ENABLED:
        return
    if _task is not None and not _task.done():
        return
    _shutdown_event = asyncio.Event()
    _task = asyncio.create_task(_run_discord_gateway(), name="gateway-discord-intake")
    logger.info("Started Discord gateway intake supervisor")


async def stop_discord_gateway_supervisor() -> None:
    global _client, _shutdown_event, _task
    if _shutdown_event is not None:
        _shutdown_event.set()
    if _client is not None and not _client.is_closed():
        await _client.close()
    if _task is not None:
        _task.cancel()
        with suppress(TimeoutError, asyncio.CancelledError):
            await asyncio.wait_for(_task, timeout=10)
    _client = None
    _task = None
    _shutdown_event = None
