"""Register the SurfSense Telegram webhook."""

from __future__ import annotations

import asyncio
import os
import re
import sys

from dotenv import load_dotenv
from telegram import Bot

from app.db import async_session_maker
from app.gateway.accounts import get_or_create_system_telegram_account

load_dotenv()

WEBHOOK_SECRET_RE = re.compile(r"^[A-Za-z0-9_-]{1,256}$")


async def main() -> int:
    token = os.getenv("TELEGRAM_SHARED_BOT_TOKEN")
    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET")
    base_url = os.getenv("GATEWAY_BASE_URL") or os.getenv("BACKEND_URL")
    if not token or not secret or not base_url:
        print(
            "Missing TELEGRAM_SHARED_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET, or GATEWAY_BASE_URL/BACKEND_URL",
            file=sys.stderr,
        )
        return 1
    if not WEBHOOK_SECRET_RE.fullmatch(secret):
        print(
            "TELEGRAM_WEBHOOK_SECRET must be 1-256 chars and contain only A-Z, a-z, 0-9, '_' or '-'",
            file=sys.stderr,
        )
        return 1

    async with async_session_maker() as session:
        account = await get_or_create_system_telegram_account(session)
        account.webhook_secret = secret
        await session.commit()
        account_id = int(account.id)

    webhook_url = (
        f"{base_url.rstrip('/')}/api/v1/gateway/webhooks/telegram/{account_id}"
    )
    bot = Bot(token=token)
    ok = await bot.set_webhook(
        url=webhook_url,
        secret_token=secret,
        allowed_updates=["message", "edited_message"],
        drop_pending_updates=True,
    )
    if not ok:
        print("Telegram rejected webhook registration", file=sys.stderr)
        return 1
    print(f"Registered Telegram webhook: {webhook_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
