"""Authentication routes for refresh token management."""

import logging
from datetime import UTC, datetime

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.auth.session_cookies import clear_session, read_refresh, write_session
from app.config import config
from app.db import User, async_session_maker, get_async_session
from app.rate_limiter import limiter
from app.schemas.auth import (
    LogoutAllResponse,
    LogoutRequest,
    LogoutResponse,
    DesktopSessionRequest,
    RefreshTokenRequest,
    RefreshTokenResponse,
    SessionResponse,
)
from app.users import SECRET, UserManager, get_auth_context, get_jwt_strategy, get_user_manager
from app.utils.refresh_tokens import (
    create_refresh_token,
    revoke_all_user_tokens,
    revoke_refresh_token,
    rotate_refresh_token,
    validate_refresh_token,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/jwt", tags=["auth"])
session_router = APIRouter(prefix="/auth", tags=["auth"])


def _access_expires_at(access_token: str) -> int:
    payload = jwt.decode(
        access_token,
        SECRET,
        algorithms=["HS256"],
        options={"verify_aud": False},
    )
    return int(payload["exp"])


def _request_access_token(request: Request) -> str | None:
    cookie_token = request.cookies.get(config.SESSION_COOKIE_NAME)
    if cookie_token:
        return cookie_token
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() == "bearer" and token:
        return token
    return None


async def _load_user(user_id) -> User | None:
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        return result.scalars().first()


@router.post("/refresh", response_model=RefreshTokenResponse)
@limiter.limit("30/minute")
async def refresh_access_token(
    request: Request,
    response: Response,
    body: RefreshTokenRequest | None = None,
):
    """
    Exchange a valid refresh token for a new access token and refresh token.
    Implements token rotation for security.
    """
    refresh_token = read_refresh(request, body)
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    rotation = await rotate_refresh_token(refresh_token)
    if not rotation:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user = await _load_user(rotation.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # Generate new access token
    strategy = get_jwt_strategy()
    access_token = await strategy.write_token(user)

    if request.cookies.get(config.REFRESH_COOKIE_NAME) and rotation.refresh_token:
        write_session(response, access_token, rotation.refresh_token, request)

    logger.info(f"Refreshed token for user {user.id}")

    return RefreshTokenResponse(
        access_token=access_token,
        refresh_token=rotation.refresh_token,
        access_expires_at=_access_expires_at(access_token),
    )


@router.post("/revoke", response_model=LogoutResponse)
async def revoke_token(
    request: Request,
    response: Response,
    body: LogoutRequest | None = None,
):
    """
    Logout current device by revoking the provided refresh token.
    Does not require authentication - just the refresh token.
    """
    refresh_token = read_refresh(request, body)
    revoked = await revoke_refresh_token(refresh_token) if refresh_token else False
    clear_session(response, request)
    if revoked:
        logger.info("User logged out from current device - token revoked")
    else:
        logger.warning("Logout called but no matching token found to revoke")
    return LogoutResponse()


@router.post("/logout-all", response_model=LogoutAllResponse)
async def logout_all_devices(
    request: Request,
    response: Response,
    body: LogoutRequest | None = None,
    session: AsyncSession = Depends(get_async_session),
    user_manager: UserManager = Depends(get_user_manager),
):
    """
    Logout from all devices by revoking all refresh tokens for the user.
    Requires valid access token.
    """
    user: User | None = None
    try:
        auth = await get_auth_context(request, session=session, user_manager=user_manager)
        if auth.is_session:
            user = auth.user
    except HTTPException:
        user = None

    if user is None:
        refresh_token = read_refresh(request, body)
        token_record = await validate_refresh_token(refresh_token) if refresh_token else None
        if token_record:
            user = await _load_user(token_record.user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    await revoke_all_user_tokens(user.id)
    clear_session(response, request)
    logger.info(f"User {user.id} logged out from all devices")
    return LogoutAllResponse()


@session_router.get("/session", response_model=SessionResponse)
async def get_session(
    request: Request,
    _auth: AuthContext = Depends(get_auth_context),
):
    access_token = _request_access_token(request)
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return SessionResponse(access_expires_at=_access_expires_at(access_token))


@session_router.post("/desktop/session", response_model=RefreshTokenResponse)
@limiter.limit("20/minute")
async def create_desktop_session(
    request: Request,
    body: DesktopSessionRequest,
    user_manager: UserManager = Depends(get_user_manager),
):
    if not body.redirect_uri.startswith("http://127.0.0.1:"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid redirect URI")
    if not config.GOOGLE_DESKTOP_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Desktop OAuth is not configured",
        )

    token_payload = {
        "client_id": config.GOOGLE_DESKTOP_CLIENT_ID,
        "code": body.code,
        "code_verifier": body.code_verifier,
        "grant_type": "authorization_code",
        "redirect_uri": body.redirect_uri,
    }
    if config.GOOGLE_DESKTOP_CLIENT_SECRET:
        token_payload["client_secret"] = config.GOOGLE_DESKTOP_CLIENT_SECRET

    async with httpx.AsyncClient(timeout=10) as client:
        token_response = await client.post("https://oauth2.googleapis.com/token", data=token_payload)
        if token_response.status_code >= 400:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="OAuth exchange failed")
        token_data = token_response.json()

    id_token = token_data.get("id_token")
    access_token = token_data.get("access_token")
    if not id_token or not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="OAuth exchange failed")

    try:
        claims = google_id_token.verify_oauth2_token(
            id_token,
            google_requests.Request(),
            config.GOOGLE_DESKTOP_CLIENT_ID,
        )
    except Exception as exc:
        logger.warning("Desktop Google id_token verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google identity token",
        ) from exc

    if not claims.get("sub") or not claims.get("email"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google identity token")

    user = await user_manager.oauth_callback(
        "google",
        access_token,
        claims["sub"],
        claims["email"],
        expires_at=(
            int(datetime.now(UTC).timestamp()) + int(token_data["expires_in"])
            if token_data.get("expires_in")
            else None
        ),
        refresh_token=token_data.get("refresh_token"),
        request=request,
        associate_by_email=True,
        is_verified_by_default=True,
    )
    app_access_token = await get_jwt_strategy().write_token(user)
    app_refresh_token = await create_refresh_token(user.id)
    return RefreshTokenResponse(
        access_token=app_access_token,
        refresh_token=app_refresh_token,
        access_expires_at=_access_expires_at(app_access_token),
    )
