"""Celery maintenance tasks for external chat surfaces."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.celery_app import celery_app
from app.db import (
    ExternalChatEventStatus,
    ExternalChatHealthStatus,
    ExternalChatInboundEvent,
    ExternalChatPlatform,
    ExternalChatAccount,
)
from app.gateway.accounts import account_token
from app.gateway.inbox import persist_inbound_event, telegram_event_dedupe_key
from app.gateway.telegram.adapter import TelegramAdapter
from app.observability.metrics import (
    record_gateway_health_check_failure,
    record_gateway_inbound_reconciled,
)
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task

logger = logging.getLogger(__name__)


@celery_app.task(name="gateway.process_inbound_event")
def process_inbound_event_task(inbox_id: int) -> None:
    logger.warning(
        "Ignoring gateway.process_inbound_event for inbox_id=%s; "
        "FastAPI owns external chat agent turn processing.",
        inbox_id,
    )
    return None


@celery_app.task(name="gateway.reconcile_inbox")
def reconcile_inbox_task() -> None:
    async def _run() -> None:
        session_maker = get_celery_session_maker()
        async with session_maker() as session:
            stale_threshold = datetime.now(UTC) - timedelta(minutes=10)
            result = await session.execute(
                update(ExternalChatInboundEvent)
                .where(
                    ExternalChatInboundEvent.status == ExternalChatEventStatus.PROCESSING,
                    ExternalChatInboundEvent.received_at < stale_threshold,
                )
                .values(
                    status=ExternalChatEventStatus.RECEIVED,
                    last_error="stale processing reset for FastAPI inbox worker",
                )
            )
            for _ in range(result.rowcount or 0):
                record_gateway_inbound_reconciled(reason="stale_processing_reset")
            await session.commit()

    return run_async_celery_task(_run)


@celery_app.task(name="gateway.health_check")
def gateway_health_check_task() -> None:
    async def _run() -> None:
        session_maker = get_celery_session_maker()
        async with session_maker() as session:
            result = await session.execute(select(ExternalChatAccount))
            accounts = list(result.scalars())
            for account in accounts:
                token = account_token(account)
                if not token or account.platform != ExternalChatPlatform.TELEGRAM:
                    continue
                try:
                    metadata = await TelegramAdapter(token).validate_credentials()
                    account.health_status = ExternalChatHealthStatus.OK
                    account.bot_username = metadata.get("username")
                except Exception:
                    logger.warning("External chat Telegram health check failed", exc_info=True)
                    account.health_status = ExternalChatHealthStatus.FAILING
                    record_gateway_health_check_failure(platform=account.platform.value)
                account.last_health_check_at = datetime.now(UTC)
            await session.commit()

    return run_async_celery_task(_run)


@celery_app.task(name="gateway.enqueue_received_sweep")
def enqueue_received_sweep_task() -> int:
    logger.info(
        "Skipping gateway.enqueue_received_sweep; "
        "FastAPI inbox worker scans RECEIVED rows directly."
    )
    return 0


@celery_app.task(name="gateway.retention_sweep")
def gateway_retention_sweep_task() -> None:
    async def _run() -> None:
        session_maker = get_celery_session_maker()
        async with session_maker() as session:
            raw_cutoff = datetime.now(UTC) - timedelta(days=30)
            delete_cutoff = datetime.now(UTC) - timedelta(days=365)
            await session.execute(
                update(ExternalChatInboundEvent)
                .where(ExternalChatInboundEvent.received_at < raw_cutoff)
                .values(raw_payload=None)
            )
            result = await session.execute(
                select(ExternalChatInboundEvent).where(
                    ExternalChatInboundEvent.received_at < delete_cutoff
                )
            )
            for event in result.scalars():
                await session.delete(event)
            await session.commit()

    return run_async_celery_task(_run)


async def enqueue_telegram_update(account_id: int, raw_update: dict) -> int | None:
    session_maker = get_celery_session_maker()
    async with session_maker() as session:
        parsed = TelegramAdapter("placeholder").parse_inbound(raw_update)
        inbox_id = await persist_inbound_event(
            session,
            account_id=account_id,
            platform=ExternalChatPlatform.TELEGRAM,
            event_dedupe_key=telegram_event_dedupe_key(raw_update["update_id"]),
            external_event_id=str(raw_update["update_id"]),
            external_message_id=parsed.external_message_id,
            event_kind=parsed.event_kind,
            raw_payload=raw_update,
        )
        await session.commit()
        return inbox_id

