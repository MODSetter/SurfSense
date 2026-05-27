"""Thin async Telegram Bot API client."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any

from telegram import Bot
from telegram.error import BadRequest, RetryAfter

from app.gateway.base.adapter import PlatformSendResult


def retry_after_seconds(value: int | timedelta) -> float:
    if isinstance(value, timedelta):
        return value.total_seconds()
    return float(value)


class TelegramClient:
    def __init__(self, token: str) -> None:
        self.token = token
        self.bot = Bot(token=token)

    async def send_message(
        self,
        *,
        chat_id: str,
        text: str,
        parse_mode: str | None = None,
        reply_to_message_id: str | None = None,
    ) -> PlatformSendResult:
        kwargs: dict[str, Any] = {}
        if parse_mode:
            kwargs["parse_mode"] = parse_mode
        if reply_to_message_id:
            kwargs["reply_to_message_id"] = int(reply_to_message_id)
        try:
            msg = await self.bot.send_message(chat_id=chat_id, text=text, **kwargs)
        except RetryAfter as exc:
            await asyncio.sleep(retry_after_seconds(exc.retry_after))
            msg = await self.bot.send_message(chat_id=chat_id, text=text, **kwargs)
        return PlatformSendResult(
            external_message_id=str(msg.message_id),
            raw_response=msg.to_dict(),
        )

    async def edit_message(
        self,
        *,
        chat_id: str,
        message_id: str,
        text: str,
        parse_mode: str | None = None,
    ) -> PlatformSendResult:
        kwargs: dict[str, Any] = {}
        if parse_mode:
            kwargs["parse_mode"] = parse_mode
        try:
            msg = await self.bot.edit_message_text(
                chat_id=chat_id,
                message_id=int(message_id),
                text=text,
                **kwargs,
            )
        except RetryAfter as exc:
            await asyncio.sleep(retry_after_seconds(exc.retry_after))
            msg = await self.bot.edit_message_text(
                chat_id=chat_id,
                message_id=int(message_id),
                text=text,
                **kwargs,
            )
        return PlatformSendResult(
            external_message_id=str(msg.message_id),
            raw_response=msg.to_dict(),
        )

    async def validate(self) -> dict[str, Any]:
        me = await self.bot.get_me()
        return me.to_dict()

    async def leave_chat(self, *, chat_id: str) -> None:
        await self.bot.leave_chat(chat_id=chat_id)

    async def get_updates(self, *, offset: int | None) -> AsyncIterator[dict[str, Any]]:
        next_offset = offset
        while True:
            updates = await self.bot.get_updates(
                offset=next_offset,
                timeout=30,
                allowed_updates=["message", "edited_message"],
            )
            for update in updates:
                next_offset = update.update_id + 1
                yield update.to_dict()


async def retry_plaintext_on_bad_markdown(call, *args, **kwargs) -> PlatformSendResult:
    try:
        return await call(*args, **kwargs)
    except BadRequest as exc:
        if "can't parse entities" not in str(exc).lower():
            raise
        kwargs["parse_mode"] = None
        return await call(*args, **kwargs)

