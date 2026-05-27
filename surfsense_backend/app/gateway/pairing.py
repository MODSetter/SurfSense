"""Pairing code lifecycle for gateway bindings."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import GatewayBindingState, GatewayConversationBinding

PAIRING_CODE_TTL = timedelta(minutes=10)


def generate_pairing_code() -> str:
    return secrets.token_urlsafe(6)


def pairing_expires_at() -> datetime:
    return datetime.now(UTC) + PAIRING_CODE_TTL


async def redeem_pairing_code(
    session: AsyncSession,
    *,
    code: str,
    external_peer_id: str,
    external_peer_kind: str,
    external_display_name: str | None,
    external_username: str | None,
    external_metadata: dict | None = None,
) -> GatewayConversationBinding | None:
    result = await session.execute(
        select(GatewayConversationBinding).where(
            GatewayConversationBinding.pairing_code == code,
            GatewayConversationBinding.state == GatewayBindingState.PENDING,
            GatewayConversationBinding.pairing_code_expires_at > datetime.now(UTC),
        )
    )
    binding = result.scalars().first()
    if binding is None:
        return None

    binding.state = GatewayBindingState.BOUND
    binding.pairing_code = None
    binding.pairing_code_expires_at = None
    binding.external_peer_id = external_peer_id
    binding.external_peer_kind = external_peer_kind
    binding.external_display_name = external_display_name
    binding.external_username = external_username
    binding.external_metadata = external_metadata or {}
    return binding

