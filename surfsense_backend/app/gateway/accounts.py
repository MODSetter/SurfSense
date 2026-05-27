"""Gateway account helpers."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import (
    GatewayAccountMode,
    GatewayHealthStatus,
    GatewayPlatform,
    GatewayPlatformAccount,
)
from app.utils.oauth_security import TokenEncryption


def account_token(account: GatewayPlatformAccount) -> str | None:
    if account.is_system_account and account.platform == GatewayPlatform.TELEGRAM:
        return config.TELEGRAM_SHARED_BOT_TOKEN
    if not account.encrypted_credentials:
        return None
    return TokenEncryption(config.SECRET_KEY or "").decrypt_token(
        account.encrypted_credentials
    )


async def get_or_create_system_telegram_account(
    session: AsyncSession,
) -> GatewayPlatformAccount:
    result = await session.execute(
        select(GatewayPlatformAccount).where(
            GatewayPlatformAccount.platform == GatewayPlatform.TELEGRAM,
            GatewayPlatformAccount.is_system_account.is_(True),
        )
    )
    account = result.scalars().first()
    if account is not None:
        return account
    account = GatewayPlatformAccount(
        platform=GatewayPlatform.TELEGRAM,
        mode=GatewayAccountMode.CLOUD_SHARED,
        is_system_account=True,
        account_metadata={
            "bot_username": config.TELEGRAM_SHARED_BOT_USERNAME,
            "webhook_secret": config.TELEGRAM_WEBHOOK_SECRET,
        },
        cursor_state={},
        health_status=GatewayHealthStatus.UNKNOWN,
    )
    session.add(account)
    await session.flush()
    return account

