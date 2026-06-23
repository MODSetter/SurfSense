"""Authentication schemas for refresh token endpoints."""

from pydantic import BaseModel


class RefreshTokenRequest(BaseModel):
    """Request body for token refresh endpoint."""

    refresh_token: str | None = None


class RefreshTokenResponse(BaseModel):
    """Response from token refresh endpoint."""

    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    access_expires_at: int


class LogoutRequest(BaseModel):
    """Request body for logout endpoint (current device)."""

    refresh_token: str | None = None


class LogoutResponse(BaseModel):
    """Response from logout endpoint (current device)."""

    detail: str = "Successfully logged out"


class LogoutAllResponse(BaseModel):
    """Response from logout all devices endpoint."""

    detail: str = "Successfully logged out from all devices"


class SessionResponse(BaseModel):
    authenticated: bool = True
    access_expires_at: int | None = None


class DesktopSessionRequest(BaseModel):
    code: str
    code_verifier: str
    redirect_uri: str


class DesktopLoginRequest(BaseModel):
    email: str
    password: str
