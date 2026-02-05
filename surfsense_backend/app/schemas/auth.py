"""Authentication schemas for refresh token endpoints."""

from pydantic import BaseModel


class RefreshTokenResponse(BaseModel):
    """Response from token refresh endpoint."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LogoutResponse(BaseModel):
    """Response from logout endpoint (current device)."""

    detail: str = "Successfully logged out"


class LogoutAllResponse(BaseModel):
    """Response from logout all devices endpoint."""

    detail: str = "Successfully logged out from all devices"
