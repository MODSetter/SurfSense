"""Utilities for managing refresh tokens."""

import hashlib
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.config import config
from app.db import RefreshToken, async_session_maker

logger = logging.getLogger(__name__)


def generate_refresh_token() -> str:
    """Generate a cryptographically secure refresh token."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Hash a token for secure storage."""
    return hashlib.sha256(token.encode()).hexdigest()


async def create_refresh_token(
    user_id: uuid.UUID,
    family_id: uuid.UUID | None = None,
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
    expires_at = datetime.now(UTC) + timedelta(
        seconds=config.REFRESH_TOKEN_LIFETIME_SECONDS
    )

    if family_id is None:
        family_id = uuid.uuid4()

    async with async_session_maker() as session:
        refresh_token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            family_id=family_id,
        )
        session.add(refresh_token)
        await session.commit()

    return token


async def validate_refresh_token(token: str) -> RefreshToken | None:
    """
    Validate a refresh token. Handles reuse detection.

    Args:
        token: The plaintext refresh token

    Returns:
        RefreshToken if valid, None otherwise
    """
    token_hash = hash_token(token)

    async with async_session_maker() as session:
        result = await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        refresh_token = result.scalars().first()

        if not refresh_token:
            return None

        # Reuse detection: revoked token used while family has active tokens
        if refresh_token.is_revoked:
            active = await session.execute(
                select(RefreshToken).where(
                    RefreshToken.family_id == refresh_token.family_id,
                    RefreshToken.is_revoked == False,  # noqa: E712
                    RefreshToken.expires_at > datetime.now(UTC),
                )
            )
            if active.scalars().first():
                # Revoke entire family
                await session.execute(
                    update(RefreshToken)
                    .where(RefreshToken.family_id == refresh_token.family_id)
                    .values(is_revoked=True)
                )
                await session.commit()
                logger.warning(f"Token reuse detected for user {refresh_token.user_id}")
            return None

        if refresh_token.is_expired:
            return None

        return refresh_token


async def rotate_refresh_token(old_token: RefreshToken) -> str:
    """Revoke old token and create new one in same family."""
    async with async_session_maker() as session:
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.id == old_token.id)
            .values(is_revoked=True)
        )
        await session.commit()

    return await create_refresh_token(old_token.user_id, old_token.family_id)


async def revoke_refresh_token(token: str) -> bool:
    """
    Revoke a single refresh token by its plaintext value.

    Args:
        token: The plaintext refresh token

    Returns:
        True if token was found and revoked, False otherwise
    """
    token_hash = hash_token(token)

    async with async_session_maker() as session:
        result = await session.execute(
            update(RefreshToken)
            .where(RefreshToken.token_hash == token_hash)
            .values(is_revoked=True)
        )
        await session.commit()
        return result.rowcount > 0


async def revoke_all_user_tokens(user_id: uuid.UUID) -> None:
    """Revoke all refresh tokens for a user (logout all devices)."""
    async with async_session_maker() as session:
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id)
            .values(is_revoked=True)
        )
        await session.commit()
