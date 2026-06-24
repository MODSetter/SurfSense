from __future__ import annotations

import asyncio
import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.db import PersonalAccessToken, User, async_session_maker

logger = logging.getLogger(__name__)

PAT_PREFIX = "ss_pat_"
PAT_TOKEN_BYTES = 32
LAST_USED_THROTTLE = timedelta(minutes=10)
_last_used_tasks: set[asyncio.Task[None]] = set()


def generate_pat() -> str:
    return f"{PAT_PREFIX}{secrets.token_urlsafe(PAT_TOKEN_BYTES)}"


def hash_pat(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def token_prefix(token: str) -> str:
    return token[:16]


async def resolve_pat(
    session: AsyncSession,
    token: str,
) -> PersonalAccessToken | None:
    now = datetime.now(UTC)
    result = await session.execute(
        select(PersonalAccessToken)
        .options(selectinload(PersonalAccessToken.user))
        .join(User)
        .where(
            PersonalAccessToken.token_hash == hash_pat(token),
            (PersonalAccessToken.expires_at.is_(None))
            | (PersonalAccessToken.expires_at > now),
            User.is_active == True,  # noqa: E712
        )
    )
    return result.scalars().first()


async def _touch_last_used(token_id: int) -> None:
    try:
        async with async_session_maker() as session:
            await session.execute(
                update(PersonalAccessToken)
                .where(PersonalAccessToken.id == token_id)
                .values(last_used_at=datetime.now(UTC))
            )
            await session.commit()
    except Exception:
        logger.exception("Failed to update PAT last_used_at for token %s", token_id)


def maybe_touch_last_used(pat: PersonalAccessToken) -> None:
    last_used_at = pat.last_used_at
    now = datetime.now(UTC)
    if last_used_at is not None and now - last_used_at < LAST_USED_THROTTLE:
        return

    task = asyncio.create_task(_touch_last_used(pat.id))
    _last_used_tasks.add(task)
    task.add_done_callback(_last_used_tasks.discard)
