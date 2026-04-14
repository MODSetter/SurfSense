"""Authentication routes for refresh token management."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
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
    Exchange the oauth2-proxy ForwardAuth session for a SurfSense JWT delivered
    via short-lived cookies.

    Flow:
      Browser → Traefik ForwardAuth → oauth2-proxy validates session
      → sets X-Auth-Request-Email → ProxyAuthMiddleware resolves/creates user
      → this endpoint reads request.state.proxy_user → issues JWT
      → sets surfsense_sso_token + surfsense_sso_refresh_token cookies (60s TTL)
      → redirects to / → page.tsx reads cookies → stores to localStorage → /dashboard

    All user provisioning (including on_after_register side effects —
    default SearchSpace, RBAC roles, system prompts) is owned by
    ProxyAuthMiddleware. This handler does not touch the User table.
    """
    user: User | None = getattr(request.state, "proxy_user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No proxy auth session — request did not pass through oauth2-proxy ForwardAuth",
        )

    # Middleware already filters inactive users; defence-in-depth re-check.
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
    cookie_opts = dict(httponly=False, secure=True, samesite="lax", max_age=60)  # noqa: C408
    response.set_cookie("surfsense_sso_token", access_token, **cookie_opts)
    response.set_cookie("surfsense_sso_refresh_token", refresh_token, **cookie_opts)

    logger.info("proxy_login: issued JWT for %s → redirecting to frontend via cookie", user.email)
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
