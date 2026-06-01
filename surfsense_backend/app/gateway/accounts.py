"""External chat account helpers."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import (
    ExternalChatAccount,
    ExternalChatAccountMode,
    ExternalChatHealthStatus,
    ExternalChatPlatform,
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


def slack_account_credentials(account: ExternalChatAccount) -> dict:
    """Decrypt Slack gateway credentials stored as encrypted JSON."""
    if not account.encrypted_credentials:
        return {}
    raw = TokenEncryption(config.SECRET_KEY or "").decrypt_token(account.encrypted_credentials)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Backward-compatible fallback if a token string was stored directly.
        return {"bot_token": raw}
    return data if isinstance(data, dict) else {}


def discord_account_credentials(account: ExternalChatAccount) -> dict:
    """Decrypt Discord gateway credentials stored as encrypted JSON."""
    if not account.encrypted_credentials:
        return {}
    raw = TokenEncryption(config.SECRET_KEY or "").decrypt_token(account.encrypted_credentials)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Backward-compatible fallback if a token string was stored directly.
        return {"bot_token": raw}
    return data if isinstance(data, dict) else {}


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


async def get_or_create_system_whatsapp_account(
    session: AsyncSession,
) -> ExternalChatAccount:
    result = await session.execute(
        select(ExternalChatAccount).where(
            ExternalChatAccount.platform == ExternalChatPlatform.WHATSAPP,
            ExternalChatAccount.is_system_account.is_(True),
        )
    )
    account = result.scalars().first()
    if account is not None:
        return account
    account = ExternalChatAccount(
        platform=ExternalChatPlatform.WHATSAPP,
        mode=ExternalChatAccountMode.CLOUD_SHARED,
        is_system_account=True,
        cursor_state={
            "phone_number_id": config.WHATSAPP_SHARED_PHONE_NUMBER_ID,
            "display_phone_number": config.WHATSAPP_SHARED_DISPLAY_PHONE_NUMBER,
            "waba_id": config.WHATSAPP_SHARED_WABA_ID,
        },
        health_status=ExternalChatHealthStatus.UNKNOWN,
    )
    session.add(account)
    await session.flush()
    return account


async def get_slack_account_by_team(
    session: AsyncSession,
    *,
    team_id: str,
) -> ExternalChatAccount | None:
    result = await session.execute(
        select(ExternalChatAccount).where(
            ExternalChatAccount.platform == ExternalChatPlatform.SLACK,
            ExternalChatAccount.is_system_account.is_(True),
            ExternalChatAccount.cursor_state["team_id"].astext == team_id,
        )
    )
    return result.scalars().first()


async def get_discord_account_by_guild(
    session: AsyncSession,
    *,
    guild_id: str,
) -> ExternalChatAccount | None:
    result = await session.execute(
        select(ExternalChatAccount).where(
            ExternalChatAccount.platform == ExternalChatPlatform.DISCORD,
            ExternalChatAccount.is_system_account.is_(True),
            ExternalChatAccount.cursor_state["guild_id"].astext == guild_id,
        )
    )
    return result.scalars().first()

