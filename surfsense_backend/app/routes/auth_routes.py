"""
Authentication routes for token verification and session management.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.db import User
from app.users import current_active_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])


class UserResponse(BaseModel):
    """User data response model."""

    id: str
    email: str
    is_active: bool
    is_superuser: bool
    is_verified: bool
    pages_limit: int
    pages_used: int
    avatar: str | None = None


class VerifyTokenResponse(BaseModel):
    """Token verification response model."""

    valid: bool
    user: UserResponse


@router.get("/verify-token", response_model=VerifyTokenResponse)
async def verify_token(
    user: User = Depends(current_active_user),
) -> VerifyTokenResponse:
    """
    Verify JWT token and return user information.

    This endpoint validates the Bearer token provided in the Authorization header
    and returns the authenticated user's information if valid.

    Authentication:
        - Requires valid JWT token in Authorization header
        - Token must not be expired (default lifetime: 1 hour)
        - User must be active

    Returns:
        VerifyTokenResponse with user data

    Raises:
        HTTPException: 401 if token is invalid or expired
        HTTPException: 403 if user is inactive
    """
    logger.info(f"Token verified successfully for user {user.email}")

    return VerifyTokenResponse(
        valid=True,
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            is_verified=user.is_verified,
            pages_limit=user.pages_limit,
            pages_used=user.pages_used,
            avatar=user.avatar,
        ),
    )
