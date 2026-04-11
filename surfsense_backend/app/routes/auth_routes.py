"""Authentication routes for refresh token management."""

import logging
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi_users.password import PasswordHelper
from sqlalchemy import select

from app.config import config
from app.db import User, async_session_maker
from app.schemas.auth import (
    LogoutAllResponse,
    LogoutRequest,
    LogoutResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
)
from app.users import current_active_user, get_jwt_strategy
from app.utils.refresh_tokens import (
    create_refresh_token,
    revoke_all_user_tokens,
    revoke_refresh_token,
    rotate_refresh_token,
    validate_refresh_token,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/jwt", tags=["auth"])


@router.get("/proxy-login")
async def proxy_login(request: Request):
    """
    Exchange X-Auth-Request-Email (injected by oauth2-proxy ForwardAuth via Traefik)
    for a SurfSense JWT + refresh token delivered via short-lived cookies.

    Flow:
      Browser → Traefik ForwardAuth → oauth2-proxy validates session
      → sets X-Auth-Request-Email → this endpoint issues JWT
      → sets surfsense_sso_token + surfsense_sso_refresh_token cookies (60s TTL)
      → redirects to / → page.tsx reads cookies → stores to localStorage → /dashboard
    """
    email = request.headers.get("x-auth-request-email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No proxy auth header — request did not pass through oauth2-proxy ForwardAuth",
        )

    email = email.strip().lower()

    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.unique().scalar_one_or_none()

        if user is None:
            # JIT provisioning — create the user on first SSO login.
            # A random password is set (unused; auth is always via the SSO proxy).
            logger.info("proxy_login: first SSO login for %s — provisioning user", email)
            _ph = PasswordHelper()
            user = User(
                id=uuid.uuid4(),
                email=email,
                hashed_password=_ph.hash(secrets.token_urlsafe(32)),
                is_active=True,
                is_verified=True,
                is_superuser=False,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
        )

    strategy = get_jwt_strategy()
    access_token = await strategy.write_token(user)
    refresh_token = await create_refresh_token(user.id)

    frontend_url = (config.NEXT_FRONTEND_URL or "http://localhost:3000").rstrip("/")

    # Deliver tokens via short-lived cookies so the frontend can pick them up at /
    # without needing a dedicated /auth/callback route (avoids Traefik path splitting).
    response = RedirectResponse(f"{frontend_url}/", status_code=302)
    cookie_opts = dict(httponly=False, secure=True, samesite="lax", max_age=60)
    response.set_cookie("surfsense_sso_token", access_token, **cookie_opts)
    response.set_cookie("surfsense_sso_refresh_token", refresh_token, **cookie_opts)

    logger.info("proxy_login: issued JWT for %s → redirecting to frontend via cookie", email)
    return response


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_access_token(request: RefreshTokenRequest):
    """
    Exchange a valid refresh token for a new access token and refresh token.
    Implements token rotation for security.
    """
    token_record = await validate_refresh_token(request.refresh_token)

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

    logger.info(f"Refreshed token for user {user.id}")

    return RefreshTokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
    )


@router.post("/revoke", response_model=LogoutResponse)
async def revoke_token(request: LogoutRequest):
    """
    Logout current device by revoking the provided refresh token.
    Does not require authentication - just the refresh token.
    """
    revoked = await revoke_refresh_token(request.refresh_token)
    if revoked:
        logger.info("User logged out from current device - token revoked")
    else:
        logger.warning("Logout called but no matching token found to revoke")
    return LogoutResponse()


@router.post("/logout-all", response_model=LogoutAllResponse)
async def logout_all_devices(user: User = Depends(current_active_user)):
    """
    Logout from all devices by revoking all refresh tokens for the user.
    Requires valid access token.
    """
    await revoke_all_user_tokens(user.id)
    logger.info(f"User {user.id} logged out from all devices")
    return LogoutAllResponse()
