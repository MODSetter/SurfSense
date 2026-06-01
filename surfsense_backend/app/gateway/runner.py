"""Telegram BYO long-poll helper for FastAPI lifespan."""

from __future__ import annotations

import hashlib
import logging
import uuid

from sqlalchemy import text

from app.db import ExternalChatPlatform, ExternalChatAccount, async_session_maker, engine
from app.gateway.inbox import persist_inbound_event, telegram_event_dedupe_key
from app.gateway.telegram.adapter import TelegramAdapter
from app.observability.metrics import record_gateway_byo_longpoll_running_delta

logger = logging.getLogger(__name__)


def _lock_key(token: str) -> int:
    digest = hashlib.sha256(f"gateway:telegram:{token}".encode()).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


async def _run_telegram_account(account_id: int, token: str) -> None:
    async with engine.connect() as conn:
        lock_key = _lock_key(token)
        got_lock = await conn.scalar(
            text("SELECT pg_try_advisory_lock(:key)"),
            {"key": lock_key},
        )
        if not got_lock:
            logger.warning("Another Telegram gateway runner is active; exiting")
            return

        record_gateway_byo_longpoll_running_delta(1, account_id=account_id)
        try:
            adapter = TelegramAdapter(token)
            async with async_session_maker() as session:
                account = await session.get(ExternalChatAccount, account_id)
                offset = None
                if account is not None:
                    offset = int((account.cursor_state or {}).get("last_update_id", 0)) + 1

            async for update in adapter.fetch_updates(offset=offset):
                request_id = f"gateway_{uuid.uuid4().hex[:16]}"
                async with async_session_maker() as session:
                    parsed = adapter.parse_inbound(update)
                    inbox_id = await persist_inbound_event(
                        session,
                        account_id=account_id,
                        platform=ExternalChatPlatform.TELEGRAM,
                        event_dedupe_key=telegram_event_dedupe_key(update["update_id"]),
                        external_event_id=str(update["update_id"]),
                        external_message_id=parsed.external_message_id,
                        event_kind=parsed.event_kind,
                        raw_payload=update,
                        request_id=request_id,
                    )
                    await session.commit()
                    if inbox_id is not None:
                        logger.debug("Persisted Telegram polling update inbox_id=%s", inbox_id)
        finally:
            record_gateway_byo_longpoll_running_delta(-1, account_id=account_id)
            await conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key})

