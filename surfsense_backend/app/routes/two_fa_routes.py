"""
Two-Factor Authentication routes.
"""

import json
import logging
import os
import secrets
from datetime import UTC, datetime, timedelta

import redis
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import User, get_async_session
from app.services.two_fa_service import two_fa_service
from app.services.security_event_service import security_event_service
from app.users import current_active_user, get_jwt_strategy

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/2fa", tags=["2fa"])

# Password context for verifying user passwords
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Redis client for temporary token storage
# Uses the same Redis as Celery for consistency
REDIS_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
_redis_client: redis.Redis | None = None

def get_redis_client() -> redis.Redis:
    """Get or create Redis client for 2FA token storage."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client

# Key prefix for 2FA temporary tokens in Redis
TEMP_TOKEN_PREFIX = "2fa_temp_token:"


def get_request_metadata(request: Request | None) -> tuple[str | None, str | None]:
    """Extract IP address and user agent from request."""
    if not request:
        return None, None

    # Get IP address (handle proxy headers)
    ip_address = request.client.host if request.client else None
    if "x-forwarded-for" in request.headers:
        ip_address = request.headers["x-forwarded-for"].split(",")[0].strip()
    elif "x-real-ip" in request.headers:
        ip_address = request.headers["x-real-ip"]

    # Get user agent
    user_agent = request.headers.get("user-agent")

    return ip_address, user_agent


class SetupResponse(BaseModel):
    """Response for 2FA setup initiation."""

    secret: str
    qr_code: str
    uri: str


class VerifyCodeRequest(BaseModel):
    """Request to verify a TOTP code."""

    code: str


class VerifySetupResponse(BaseModel):
    """Response for 2FA setup verification."""

    success: bool
    backup_codes: list[str] | None = None


class StatusResponse(BaseModel):
    """Response for 2FA status."""

    enabled: bool
    has_backup_codes: bool


class DisableRequest(BaseModel):
    """Request to disable 2FA."""

    code: str


class BackupCodesResponse(BaseModel):
    """Response with new backup codes."""

    backup_codes: list[str]


class TwoFALoginRequest(BaseModel):
    """Request for 2FA verification during login."""

    temporary_token: str
    code: str


class TwoFALoginResponse(BaseModel):
    """Response for successful 2FA login."""

    access_token: str
    token_type: str


@router.get("/status", response_model=StatusResponse)
async def get_2fa_status(
    user: User = Depends(current_active_user),
):
    """
    Get the current 2FA status for the user.
    """
    has_backup = bool(user.backup_codes and len(user.backup_codes) > 0)

    return StatusResponse(
        enabled=user.two_fa_enabled,
        has_backup_codes=has_backup,
    )


@router.post("/setup", response_model=SetupResponse)
async def setup_2fa(
    request: Request,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Initialize 2FA setup by generating a new secret and QR code.

    The user must verify this setup by calling /verify-setup with a valid code
    before 2FA is enabled.
    """
    if user.two_fa_enabled:
        raise HTTPException(
            status_code=400,
            detail="2FA is already enabled. Disable it first to reconfigure.",
        )

    # Generate new secret
    secret = two_fa_service.generate_secret()

    # Generate QR code
    qr_code = two_fa_service.generate_qr_code(secret, user.email)

    # Get URI for manual entry
    uri = two_fa_service.get_totp_uri(secret, user.email)

    # Store secret temporarily (not enabled yet)
    user.totp_secret = secret
    await session.commit()

    # Log security event
    ip_address, user_agent = get_request_metadata(request)
    await security_event_service.log_2fa_setup_initiated(
        session=session,
        user_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    logger.info(f"2FA setup initiated for user {user.email}")

    return SetupResponse(
        secret=secret,
        qr_code=qr_code,
        uri=uri,
    )


@router.post("/verify-setup", response_model=VerifySetupResponse)
async def verify_2fa_setup(
    code_request: VerifyCodeRequest,
    http_request: Request,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Verify the 2FA setup by confirming the first TOTP code.

    This enables 2FA for the user and generates backup codes.
    """
    ip_address, user_agent = get_request_metadata(http_request)

    if user.two_fa_enabled:
        raise HTTPException(
            status_code=400,
            detail="2FA is already enabled.",
        )

    if not user.totp_secret:
        raise HTTPException(
            status_code=400,
            detail="2FA setup not initiated. Call /setup first.",
        )

    # Verify the code
    is_valid = two_fa_service.verify_totp(user.totp_secret, code_request.code)

    # Log verification attempt
    await security_event_service.log_2fa_verification(
        session=session,
        user_id=user.id,
        success=is_valid,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail="Invalid verification code. Please try again.",
        )

    # Generate backup codes
    plain_codes, hashed_codes = two_fa_service.generate_backup_codes(10)

    # Enable 2FA
    user.two_fa_enabled = True
    user.backup_codes = hashed_codes
    await session.commit()

    # Log 2FA enabled
    await security_event_service.log_2fa_enabled(
        session=session,
        user_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    logger.info(f"2FA enabled for user {user.email}")

    return VerifySetupResponse(
        success=True,
        backup_codes=plain_codes,
    )


@router.post("/disable")
async def disable_2fa(
    code_request: DisableRequest,
    http_request: Request,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Disable 2FA for the user.

    Requires a valid TOTP code or backup code for security.
    """
    ip_address, user_agent = get_request_metadata(http_request)

    if not user.two_fa_enabled:
        raise HTTPException(
            status_code=400,
            detail="2FA is not enabled.",
        )

    # Verify with TOTP code
    is_valid = two_fa_service.verify_totp(user.totp_secret, code_request.code)
    used_backup_code = False

    # If not valid, try backup codes
    if not is_valid and user.backup_codes:
        is_valid, used_index = two_fa_service.verify_backup_code(
            code_request.code, user.backup_codes
        )
        if is_valid and used_index is not None:
            # Remove used backup code
            user.backup_codes[used_index] = None
            used_backup_code = True

    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail="Invalid code. Please provide a valid TOTP or backup code.",
        )

    # Log backup code usage if applicable
    if used_backup_code:
        await security_event_service.log_backup_code_used(
            session=session,
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    # Disable 2FA
    user.two_fa_enabled = False
    user.totp_secret = None
    user.backup_codes = None
    await session.commit()

    # Log 2FA disabled
    await security_event_service.log_2fa_disabled(
        session=session,
        user_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    logger.info(f"2FA disabled for user {user.email}")

    return {"success": True, "message": "2FA has been disabled."}


@router.post("/backup-codes", response_model=BackupCodesResponse)
async def regenerate_backup_codes(
    code_request: VerifyCodeRequest,
    http_request: Request,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Generate new backup codes.

    Requires a valid TOTP code for security. This invalidates all previous backup codes.
    """
    ip_address, user_agent = get_request_metadata(http_request)

    if not user.two_fa_enabled:
        raise HTTPException(
            status_code=400,
            detail="2FA is not enabled.",
        )

    # Verify with TOTP code
    if not two_fa_service.verify_totp(user.totp_secret, code_request.code):
        raise HTTPException(
            status_code=400,
            detail="Invalid verification code.",
        )

    # Generate new backup codes
    plain_codes, hashed_codes = two_fa_service.generate_backup_codes(10)

    # Update backup codes
    user.backup_codes = hashed_codes
    await session.commit()

    # Log backup codes regenerated
    await security_event_service.log_backup_codes_regenerated(
        session=session,
        user_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    logger.info(f"Backup codes regenerated for user {user.email}")

    return BackupCodesResponse(backup_codes=plain_codes)


def store_temporary_token(token: str, user_id: str, expires_in_minutes: int = 5):
    """Store a temporary token for 2FA verification in Redis."""
    try:
        client = get_redis_client()
        key = f"{TEMP_TOKEN_PREFIX}{token}"
        data = json.dumps({"user_id": user_id})
        # Set with TTL for automatic expiration
        client.setex(key, expires_in_minutes * 60, data)
    except redis.RedisError as e:
        logger.error(f"Failed to store 2FA token in Redis: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to process 2FA request. Please try again.",
        )


def get_user_id_from_token(token: str) -> str | None:
    """Get user ID from temporary token if valid and not expired."""
    try:
        client = get_redis_client()
        key = f"{TEMP_TOKEN_PREFIX}{token}"
        data = client.get(key)
        if not data:
            return None
        return json.loads(data)["user_id"]
    except redis.RedisError as e:
        logger.error(f"Failed to retrieve 2FA token from Redis: {e}")
        return None
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Invalid 2FA token data: {e}")
        return None


def invalidate_temporary_token(token: str):
    """Invalidate a temporary token after use."""
    try:
        client = get_redis_client()
        key = f"{TEMP_TOKEN_PREFIX}{token}"
        client.delete(key)
    except redis.RedisError as e:
        logger.error(f"Failed to invalidate 2FA token in Redis: {e}")


class LoginResponse(BaseModel):
    """Response for login attempt."""

    access_token: str | None = None
    token_type: str | None = None
    requires_2fa: bool = False
    temporary_token: str | None = None


@router.post("/login", response_model=LoginResponse)
async def login_with_2fa(
    form_data: OAuth2PasswordRequestForm = Depends(),
    http_request: Request = None,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Login endpoint that handles 2FA.

    If 2FA is enabled, returns a temporary token that must be verified
    with /verify endpoint. Otherwise, returns the access token directly.
    """
    ip_address, user_agent = get_request_metadata(http_request)

    # Find user by email
    result = await session.execute(
        select(User).where(User.email == form_data.username)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=400,
            detail="Incorrect email or password",
        )

    # Verify password
    if not pwd_context.verify(form_data.password, user.hashed_password):
        # Log failed password login
        await security_event_service.log_password_login(
            session=session,
            user_id=user.id,
            success=False,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        raise HTTPException(
            status_code=400,
            detail="Incorrect email or password",
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=400,
            detail="User is inactive",
        )

    # Check if 2FA is enabled
    if user.two_fa_enabled:
        # Generate temporary token
        temp_token = f"{user.id}:{secrets.token_hex(16)}"
        store_temporary_token(temp_token, str(user.id))

        logger.info(f"2FA required for user {user.email}")

        return LoginResponse(
            requires_2fa=True,
            temporary_token=temp_token,
        )

    # No 2FA - generate JWT directly
    jwt_strategy = get_jwt_strategy()
    token = await jwt_strategy.write_token(user)

    # Log successful password login
    await security_event_service.log_password_login(
        session=session,
        user_id=user.id,
        success=True,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    logger.info(f"User {user.email} logged in successfully")

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        requires_2fa=False,
    )


@router.post("/verify", response_model=TwoFALoginResponse)
async def verify_2fa_login(
    login_request: TwoFALoginRequest,
    http_request: Request,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Verify 2FA code and complete login.

    Called after /login when 2FA is required.
    """
    ip_address, user_agent = get_request_metadata(http_request)

    # Get user ID from temporary token
    user_id = get_user_id_from_token(login_request.temporary_token)

    if not user_id:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired temporary token. Please login again.",
        )

    # Get user
    result = await session.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        invalidate_temporary_token(login_request.temporary_token)
        raise HTTPException(
            status_code=400,
            detail="User not found",
        )

    # Verify TOTP code
    is_valid = two_fa_service.verify_totp(user.totp_secret, login_request.code)
    used_backup_code = False

    # If not valid, try backup codes
    # Filter out any None values from previous usage
    valid_backup_codes = [c for c in (user.backup_codes or []) if c is not None]
    if not is_valid and valid_backup_codes:
        is_valid, used_index = two_fa_service.verify_backup_code(
            login_request.code, valid_backup_codes
        )
        if is_valid and used_index is not None:
            # Remove used backup code entirely (not replace with None)
            valid_backup_codes.pop(used_index)
            user.backup_codes = valid_backup_codes
            await session.commit()
            used_backup_code = True
            logger.info(f"Backup code used for user {user.email}")

    # Log 2FA login attempt
    await security_event_service.log_2fa_login(
        session=session,
        user_id=user.id,
        success=is_valid,
        ip_address=ip_address,
        user_agent=user_agent,
        details={"used_backup_code": used_backup_code} if used_backup_code else None,
    )

    # Log backup code usage if applicable
    if used_backup_code:
        await security_event_service.log_backup_code_used(
            session=session,
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail="Invalid verification code",
        )

    # Invalidate temporary token
    invalidate_temporary_token(login_request.temporary_token)

    # Generate JWT
    jwt_strategy = get_jwt_strategy()
    token = await jwt_strategy.write_token(user)

    logger.info(f"User {user.email} completed 2FA login")

    return TwoFALoginResponse(
        access_token=token,
        token_type="bearer",
    )
