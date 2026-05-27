"""External chat account helpers."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import (
    ExternalChatAccountMode,
    ExternalChatHealthStatus,
    ExternalChatPlatform,
    ExternalChatAccount,
)
from app.utils.oauth_security import TokenEncryption


def account_token(account: ExternalChatAccount) -> str | None:
    if account.is_system_account and account.platform == ExternalChatPlatform.TELEGRAM:
        return config.TELEGRAM_SHARED_BOT_TOKEN
    if not account.encrypted_credentials:
        return None
    return TokenEncryption(config.SECRET_KEY or "").decrypt_token(
        account.encrypted_credentials
    )


async def get_or_create_system_telegram_account(
    session: AsyncSession,
) -> ExternalChatAccount:
    result = await session.execute(
        select(ExternalChatAccount).where(
            ExternalChatAccount.platform == ExternalChatPlatform.TELEGRAM,
            ExternalChatAccount.is_system_account.is_(True),
        )
    )
    account = result.scalars().first()
    if account is not None:
        return account
    account = ExternalChatAccount(
        platform=ExternalChatPlatform.TELEGRAM,
        mode=ExternalChatAccountMode.CLOUD_SHARED,
        is_system_account=True,
        bot_username=config.TELEGRAM_SHARED_BOT_USERNAME,
        webhook_secret=config.TELEGRAM_WEBHOOK_SECRET,
        cursor_state={},
        health_status=ExternalChatHealthStatus.UNKNOWN,
    )
    session.add(account)
    await session.flush()
    return account

