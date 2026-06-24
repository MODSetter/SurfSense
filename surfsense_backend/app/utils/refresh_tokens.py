"""Utilities for managing refresh tokens."""

import hashlib
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.config import config
from app.db import RefreshToken, async_session_maker

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RefreshRotationResult:
    user_id: uuid.UUID
    refresh_token: str | None
    access_only: bool = False


def generate_refresh_token() -> str:
    """Generate a cryptographically secure refresh token."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Hash a token for secure storage."""
    return hashlib.sha256(token.encode()).hexdigest()


async def create_refresh_token(
    user_id: uuid.UUID,
    family_id: uuid.UUID | None = None,
    absolute_expiry: datetime | None = None,
) -> str:
    """
    Create and store a new refresh token for a user.

    Args:
        user_id: The user's ID
        family_id: Optional family ID for token rotation

    Returns:
        The plaintext refresh token
    """
    token = generate_refresh_token()
    token_hash = hash_token(token)
    now = datetime.now(UTC)
    if absolute_expiry is None:
        absolute_expiry = now + timedelta(
            seconds=config.REFRESH_ABSOLUTE_LIFETIME_SECONDS
        )
    expires_at = min(
        now + timedelta(seconds=config.REFRESH_TOKEN_LIFETIME_SECONDS),
        absolute_expiry,
    )

    if family_id is None:
        family_id = uuid.uuid4()

    async with async_session_maker() as session:
        refresh_token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            family_id=family_id,
            absolute_expiry=absolute_expiry,
        )
        session.add(refresh_token)
        await session.commit()

    return token


async def validate_refresh_token(token: str) -> RefreshToken | None:
    """Validate an active refresh token without rotating it."""
    token_hash = hash_token(token)

    async with async_session_maker() as session:
        result = await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        refresh_token = result.scalars().first()

        if not refresh_token:
            return None

        now = datetime.now(UTC)
        if (
            refresh_token.revoked_at is not None
            or now >= refresh_token.expires_at
            or (
                refresh_token.absolute_expiry is not None
                and now >= refresh_token.absolute_expiry
            )
        ):
            return None

        return refresh_token


async def rotate_refresh_token(token: str) -> RefreshRotationResult | None:
    """Atomically rotate a refresh token with access-only grace."""
    token_hash = hash_token(token)
    now = datetime.now(UTC)
    grace_window = timedelta(seconds=config.REFRESH_ROTATION_GRACE_SECONDS)

    async with async_session_maker() as session:
        async with session.begin():
            result = await session.execute(
                select(RefreshToken)
                .where(RefreshToken.token_hash == token_hash)
                .with_for_update()
            )
            refresh_token = result.scalars().first()

            if not refresh_token:
                return None
            user_id = refresh_token.user_id

            if refresh_token.revoked_at is not None:
                if (
                    now - refresh_token.revoked_at <= grace_window
                    and now < refresh_token.expires_at
                ):
                    return RefreshRotationResult(
                        user_id=user_id,
                        refresh_token=None,
                        access_only=True,
                    )

                await session.execute(
                    update(RefreshToken)
                    .where(RefreshToken.family_id == refresh_token.family_id)
                    .values(revoked_at=now, expires_at=now)
                )
                logger.warning(f"Token reuse detected for user {user_id}")
                return None

            if now >= refresh_token.expires_at:
                return None

            family_cap = refresh_token.absolute_expiry or (
                now + timedelta(seconds=config.REFRESH_ABSOLUTE_LIFETIME_SECONDS)
            )
            if now >= family_cap:
                return None

            new_plaintext = generate_refresh_token()
            child = RefreshToken(
                user_id=user_id,
                token_hash=hash_token(new_plaintext),
                expires_at=min(
                    now + timedelta(seconds=config.REFRESH_TOKEN_LIFETIME_SECONDS),
                    family_cap,
                ),
                family_id=refresh_token.family_id,
                absolute_expiry=family_cap,
            )
            session.add(child)
            refresh_token.revoked_at = now
            refresh_token.absolute_expiry = family_cap

        return RefreshRotationResult(
            user_id=user_id,
            refresh_token=new_plaintext,
            access_only=False,
        )


async def revoke_refresh_token(token: str) -> bool:
    """
    Revoke a single refresh token by its plaintext value.

    Args:
        token: The plaintext refresh token

    Returns:
        True if token was found and revoked, False otherwise
    """
    token_hash = hash_token(token)
    now = datetime.now(UTC)

    async with async_session_maker() as session:
        result = await session.execute(
            update(RefreshToken)
            .where(RefreshToken.token_hash == token_hash)
            .values(revoked_at=now, expires_at=now)
        )
        await session.commit()
        return result.rowcount > 0


async def revoke_all_user_tokens(user_id: uuid.UUID) -> None:
    """Revoke all refresh tokens for a user (logout all devices)."""
    now = datetime.now(UTC)
    async with async_session_maker() as session:
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id)
            .values(revoked_at=now, expires_at=now)
        )
        await session.commit()
