"""Durable gateway inbox helpers."""

from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import ExternalChatInboundEvent, ExternalChatPlatform


def telegram_event_dedupe_key(update_id: int | str) -> str:
    return f"update:{update_id}"


def slack_event_dedupe_key(event_id: int | str) -> str:
    return f"slack_event:{event_id}"


def discord_message_dedupe_key(message_id: int | str) -> str:
    return f"discord_message:{message_id}"


async def persist_inbound_event(
    session: AsyncSession,
    *,
    account_id: int,
    platform: ExternalChatPlatform,
    event_dedupe_key: str,
    event_kind: str,
    raw_payload: dict,
    external_event_id: str | None = None,
    external_message_id: str | None = None,
    request_id: str | None = None,
) -> int | None:
    stmt = (
        insert(ExternalChatInboundEvent)
        .values(
            account_id=account_id,
            platform=platform,
            event_dedupe_key=event_dedupe_key,
            external_event_id=external_event_id,
            external_message_id=external_message_id,
            event_kind=event_kind,
            raw_payload=raw_payload,
            request_id=request_id,
        )
        .on_conflict_do_nothing(
            index_elements=["account_id", "event_dedupe_key"],
        )
        .returning(ExternalChatInboundEvent.id)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
