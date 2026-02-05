"""Authentication routes for refresh token management."""

import logging

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import select

from app.db import User, async_session_maker
from app.schemas.auth import LogoutAllResponse, LogoutResponse, RefreshTokenResponse
from app.users import current_active_user, get_jwt_strategy
from app.utils.auth_cookies import (
    REFRESH_TOKEN_COOKIE_NAME,
    delete_refresh_token_cookie,
    set_refresh_token_cookie,
)
from app.utils.refresh_tokens import (
    revoke_all_user_tokens,
    revoke_refresh_token,
    rotate_refresh_token,
    validate_refresh_token,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/jwt", tags=["auth"])


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_access_token(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_TOKEN_COOKIE_NAME),
):
    """
    Exchange a valid refresh token for a new access token and refresh token.
    Reads refresh token from HTTP-only cookie. Implements token rotation for security.
    """
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found",
        )

    token_record = await validate_refresh_token(refresh_token)

    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Get user from token record
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.id == token_record.user_id)
        )
        user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # Generate new access token
    strategy = get_jwt_strategy()
    access_token = await strategy.write_token(user)

    # Rotate refresh token
    new_refresh_token = await rotate_refresh_token(token_record)

    # Set the new refresh token in cookie
    set_refresh_token_cookie(response, new_refresh_token)

    logger.info(f"Refreshed token for user {user.id}")

    return RefreshTokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_TOKEN_COOKIE_NAME),
):
    """
    Logout current device by revoking the refresh token from cookie.
    """
    if refresh_token:
        await revoke_refresh_token(refresh_token)

    # Always delete the cookie
    delete_refresh_token_cookie(response)

    logger.info("User logged out from current device")
    return LogoutResponse()


@router.post("/logout-all", response_model=LogoutAllResponse)
async def logout_all_devices(
    response: Response,
    user: User = Depends(current_active_user),
):
    """
    Logout from all devices by revoking all refresh tokens for the user.
    Requires valid access token.
    """
    await revoke_all_user_tokens(user.id)

    # Delete the cookie on current device
    delete_refresh_token_cookie(response)

    logger.info(f"User {user.id} logged out from all devices")
    return LogoutAllResponse()
