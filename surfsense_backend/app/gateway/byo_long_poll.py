"""FastAPI lifespan integration for self-hosted BYO Telegram long-polling."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.config import config
from app.db import ExternalChatPlatform, ExternalChatAccount, async_session_maker
from app.gateway.accounts import account_token
from app.gateway.runner import _run_telegram_account

logger = logging.getLogger(__name__)

_tasks: set[asyncio.Task[None]] = set()
_shutdown_event: asyncio.Event | None = None


async def _sleep_or_shutdown(seconds: float) -> None:
    if _shutdown_event is None:
        await asyncio.sleep(seconds)
        return
    try:
        await asyncio.wait_for(_shutdown_event.wait(), timeout=seconds)
    except TimeoutError:
        return


async def _byo_account_supervisor(account_id: int, token: str) -> None:
    while _shutdown_event is None or not _shutdown_event.is_set():
        try:
            await _run_telegram_account(account_id, token)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "BYO Telegram long-poll failed account_id=%s; retrying in 30s",
                account_id,
            )
        await _sleep_or_shutdown(30)


async def start_byo_long_poll_supervisors() -> None:
    """Start one BYO long-poll supervisor per active non-system Telegram account."""

    global _shutdown_event
    if config.GATEWAY_TELEGRAM_INTAKE_MODE != "longpoll":
        return
    if _tasks:
        return

    _shutdown_event = asyncio.Event()
    async with async_session_maker() as session:
        result = await session.execute(
            select(ExternalChatAccount).where(
                ExternalChatAccount.platform == ExternalChatPlatform.TELEGRAM,
                ExternalChatAccount.is_system_account.is_(False),
                ExternalChatAccount.suspended_at.is_(None),
            )
        )
        accounts = list(result.scalars())

    for account in accounts:
        token = account_token(account)
        if not token:
            continue
        task = asyncio.create_task(
            _byo_account_supervisor(int(account.id), token),
            name=f"gateway-byo-telegram-{account.id}",
        )
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)
        logger.info("Started BYO Telegram long-poll supervisor account_id=%s", account.id)


async def stop_byo_long_poll_supervisors() -> None:
    """Cancel and await all BYO long-poll supervisors."""

    global _shutdown_event
    if _shutdown_event is not None:
        _shutdown_event.set()
    tasks = list(_tasks)
    for task in tasks:
        task.cancel()
    if tasks:
        try:
            await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=10)
        except TimeoutError:
            logger.warning("Timed out waiting for BYO Telegram long-poll supervisors to stop")
    _tasks.clear()
    _shutdown_event = None

