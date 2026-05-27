"""Durable gateway inbox helpers."""

from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import GatewayInboundEvent, GatewayPlatform


def telegram_event_dedupe_key(update_id: int | str) -> str:
    return f"update:{update_id}"


async def persist_inbound_event(
    session: AsyncSession,
    *,
    account_id: int,
    platform: GatewayPlatform,
    event_dedupe_key: str,
    event_kind: str,
    raw_payload: dict,
    external_event_id: str | None = None,
    external_message_id: str | None = None,
) -> int | None:
    stmt = (
        insert(GatewayInboundEvent)
        .values(
            account_id=account_id,
            platform=platform,
            event_dedupe_key=event_dedupe_key,
            external_event_id=external_event_id,
            external_message_id=external_message_id,
            event_kind=event_kind,
            raw_payload=raw_payload,
        )
        .on_conflict_do_nothing(
            index_elements=["account_id", "event_dedupe_key"],
        )
        .returning(GatewayInboundEvent.id)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

