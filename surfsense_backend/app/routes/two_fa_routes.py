"""
Two-Factor Authentication routes.
"""

import logging
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import User, get_async_session
from app.services.two_fa_service import two_fa_service
from app.users import current_active_user, get_jwt_strategy

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/2fa", tags=["2fa"])

# Password context for verifying user passwords
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# In-memory store for temporary tokens (use Redis in production)
# Format: {token: {"user_id": str, "expires_at": datetime}}
_temp_tokens: dict[str, dict] = {}


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

    logger.info(f"2FA setup initiated for user {user.email}")

    return SetupResponse(
        secret=secret,
        qr_code=qr_code,
        uri=uri,
    )


@router.post("/verify-setup", response_model=VerifySetupResponse)
async def verify_2fa_setup(
    request: VerifyCodeRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Verify the 2FA setup by confirming the first TOTP code.

    This enables 2FA for the user and generates backup codes.
    """
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
    if not two_fa_service.verify_totp(user.totp_secret, request.code):
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

    logger.info(f"2FA enabled for user {user.email}")

    return VerifySetupResponse(
        success=True,
        backup_codes=plain_codes,
    )


@router.post("/disable")
async def disable_2fa(
    request: DisableRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Disable 2FA for the user.

    Requires a valid TOTP code or backup code for security.
    """
    if not user.two_fa_enabled:
        raise HTTPException(
            status_code=400,
            detail="2FA is not enabled.",
        )

    # Verify with TOTP code
    is_valid = two_fa_service.verify_totp(user.totp_secret, request.code)

    # If not valid, try backup codes
    if not is_valid and user.backup_codes:
        is_valid, used_index = two_fa_service.verify_backup_code(
            request.code, user.backup_codes
        )
        if is_valid and used_index is not None:
            # Remove used backup code
            user.backup_codes[used_index] = None

    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail="Invalid code. Please provide a valid TOTP or backup code.",
        )

    # Disable 2FA
    user.two_fa_enabled = False
    user.totp_secret = None
    user.backup_codes = None
    await session.commit()

    logger.info(f"2FA disabled for user {user.email}")

    return {"success": True, "message": "2FA has been disabled."}


@router.post("/backup-codes", response_model=BackupCodesResponse)
async def regenerate_backup_codes(
    request: VerifyCodeRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Generate new backup codes.

    Requires a valid TOTP code for security. This invalidates all previous backup codes.
    """
    if not user.two_fa_enabled:
        raise HTTPException(
            status_code=400,
            detail="2FA is not enabled.",
        )

    # Verify with TOTP code
    if not two_fa_service.verify_totp(user.totp_secret, request.code):
        raise HTTPException(
            status_code=400,
            detail="Invalid verification code.",
        )

    # Generate new backup codes
    plain_codes, hashed_codes = two_fa_service.generate_backup_codes(10)

    # Update backup codes
    user.backup_codes = hashed_codes
    await session.commit()

    logger.info(f"Backup codes regenerated for user {user.email}")

    return BackupCodesResponse(backup_codes=plain_codes)


def store_temporary_token(token: str, user_id: str, expires_in_minutes: int = 5):
    """Store a temporary token for 2FA verification."""
    expires_at = datetime.now(UTC) + timedelta(minutes=expires_in_minutes)
    _temp_tokens[token] = {
        "user_id": user_id,
        "expires_at": expires_at,
    }

    # Clean up expired tokens
    current_time = datetime.now(UTC)
    expired = [k for k, v in _temp_tokens.items() if v["expires_at"] < current_time]
    for k in expired:
        del _temp_tokens[k]


def get_user_id_from_token(token: str) -> str | None:
    """Get user ID from temporary token if valid and not expired."""
    if token not in _temp_tokens:
        return None

    token_data = _temp_tokens[token]
    if token_data["expires_at"] < datetime.now(UTC):
        del _temp_tokens[token]
        return None

    return token_data["user_id"]


def invalidate_temporary_token(token: str):
    """Invalidate a temporary token after use."""
    if token in _temp_tokens:
        del _temp_tokens[token]


class LoginResponse(BaseModel):
    """Response for login attempt."""

    access_token: str | None = None
    token_type: str | None = None
    requires_2fa: bool = False
    temporary_token: str | None = None


@router.post("/login", response_model=LoginResponse)
async def login_with_2fa(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Login endpoint that handles 2FA.

    If 2FA is enabled, returns a temporary token that must be verified
    with /verify endpoint. Otherwise, returns the access token directly.
    """
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

    logger.info(f"User {user.email} logged in successfully")

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        requires_2fa=False,
    )


@router.post("/verify", response_model=TwoFALoginResponse)
async def verify_2fa_login(
    request: TwoFALoginRequest,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Verify 2FA code and complete login.

    Called after /login when 2FA is required.
    """
    # Get user ID from temporary token
    user_id = get_user_id_from_token(request.temporary_token)

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
        invalidate_temporary_token(request.temporary_token)
        raise HTTPException(
            status_code=400,
            detail="User not found",
        )

    # Verify TOTP code
    is_valid = two_fa_service.verify_totp(user.totp_secret, request.code)

    # If not valid, try backup codes
    if not is_valid and user.backup_codes:
        is_valid, used_index = two_fa_service.verify_backup_code(
            request.code, user.backup_codes
        )
        if is_valid and used_index is not None:
            # Remove used backup code
            backup_codes = list(user.backup_codes)
            backup_codes[used_index] = None
            user.backup_codes = backup_codes
            await session.commit()
            logger.info(f"Backup code used for user {user.email}")

    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail="Invalid verification code",
        )

    # Invalidate temporary token
    invalidate_temporary_token(request.temporary_token)

    # Generate JWT
    jwt_strategy = get_jwt_strategy()
    token = await jwt_strategy.write_token(user)

    logger.info(f"User {user.email} completed 2FA login")

    return TwoFALoginResponse(
        access_token=token,
        token_type="bearer",
    )
