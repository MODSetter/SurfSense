"""Long-lived messaging gateway runner."""

from __future__ import annotations

import asyncio
import hashlib
import logging

from sqlalchemy import select, text

from app.db import GatewayPlatform, GatewayPlatformAccount, async_session_maker, engine
from app.gateway.accounts import account_token
from app.gateway.inbox import persist_inbound_event, telegram_event_dedupe_key
from app.gateway.inbox_processor import claim_next_inbound_event, process_inbound_event
from app.gateway.telegram.adapter import TelegramAdapter

logger = logging.getLogger(__name__)


def _lock_key(token: str) -> int:
    digest = hashlib.sha256(f"gateway:telegram:{token}".encode()).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


class GatewayRunner:
    async def run(self) -> None:
        logger.info("Gateway runner started. Waiting for inbound events.")
        tasks = [asyncio.create_task(self._process_inbox_forever())]

        async with async_session_maker() as session:
            result = await session.execute(
                select(GatewayPlatformAccount).where(
                    GatewayPlatformAccount.platform == GatewayPlatform.TELEGRAM,
                    GatewayPlatformAccount.is_system_account.is_(False),
                    GatewayPlatformAccount.suspended_at.is_(None),
                )
            )
            accounts = list(result.scalars())

        for account in accounts:
            token = account_token(account)
            if not token:
                continue
            logger.info("Starting Telegram long-poll loop for account_id=%s", account.id)
            tasks.append(asyncio.create_task(self._run_telegram_account(account.id, token)))

        await asyncio.gather(*tasks)

    async def _process_inbox_forever(self) -> None:
        logger.info("Gateway inbox processor started")
        while True:
            try:
                inbox_id = await claim_next_inbound_event()
                if inbox_id is None:
                    await asyncio.sleep(0.5)
                    continue
                logger.info("Gateway processing inbox_id=%s", inbox_id)
                await process_inbound_event(inbox_id)
                logger.info("Gateway processed inbox_id=%s", inbox_id)
            except Exception:
                logger.exception("Gateway inbox processor failed one iteration")
                await asyncio.sleep(1)

    async def _run_telegram_account(self, account_id: int, token: str) -> None:
        async with engine.connect() as conn:
            got_lock = await conn.scalar(
                text("SELECT pg_try_advisory_lock(:key)"),
                {"key": _lock_key(token)},
            )
            if not got_lock:
                logger.warning("Another Telegram gateway runner is active; exiting")
                return

            adapter = TelegramAdapter(token)
            async with async_session_maker() as session:
                account = await session.get(GatewayPlatformAccount, account_id)
                offset = None
                if account is not None:
                    offset = int((account.cursor_state or {}).get("last_update_id", 0)) + 1

            async for update in adapter.fetch_updates(offset=offset):
                async with async_session_maker() as session:
                    parsed = adapter.parse_inbound(update)
                    inbox_id = await persist_inbound_event(
                        session,
                        account_id=account_id,
                        platform=GatewayPlatform.TELEGRAM,
                        event_dedupe_key=telegram_event_dedupe_key(update["update_id"]),
                        external_event_id=str(update["update_id"]),
                        external_message_id=parsed.external_message_id,
                        event_kind=parsed.event_kind,
                        raw_payload=update,
                    )
                    await session.commit()
                    if inbox_id is not None:
                        logger.debug("Persisted Telegram polling update inbox_id=%s", inbox_id)

