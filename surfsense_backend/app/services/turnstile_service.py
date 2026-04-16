"""Cloudflare Turnstile CAPTCHA verification service."""

from __future__ import annotations

import logging

import httpx

from app.config import config

logger = logging.getLogger(__name__)

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


async def verify_turnstile_token(token: str, remote_ip: str | None = None) -> bool:
    """Verify a Turnstile response token with Cloudflare.

    Returns True when the token is valid and the challenge was solved by a
    real user.  Returns False (never raises) on network errors or invalid
    tokens so callers can treat it as a simple boolean gate.
    """
    if not config.TURNSTILE_ENABLED:
        return True

    secret = config.TURNSTILE_SECRET_KEY
    if not secret:
        logger.warning("TURNSTILE_SECRET_KEY is not set; skipping verification")
        return True

    payload: dict[str, str] = {
        "secret": secret,
        "response": token,
    }
    if remote_ip:
        payload["remoteip"] = remote_ip

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(TURNSTILE_VERIFY_URL, data=payload)
            resp.raise_for_status()
            data = resp.json()
            success = data.get("success", False)
            if not success:
                logger.info(
                    "Turnstile verification failed: %s",
                    data.get("error-codes", []),
                )
            return bool(success)
    except Exception:
        logger.exception("Turnstile verification request failed")
        return False
