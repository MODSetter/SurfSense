"""Utilities for managing authentication cookies."""

from fastapi import Response

from app.config import config

REFRESH_TOKEN_COOKIE_NAME = "refresh_token"


def set_refresh_token_cookie(response: Response, token: str) -> None:
    """Set the refresh token as an HTTP-only cookie."""
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        value=token,
        max_age=config.REFRESH_TOKEN_LIFETIME_SECONDS,
        httponly=True,
        secure=True,  # Only send over HTTPS
        samesite="lax",
    )


def delete_refresh_token_cookie(response: Response) -> None:
    """Delete the refresh token cookie."""
    response.delete_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        httponly=True,
        secure=True,
        samesite="lax",
    )
