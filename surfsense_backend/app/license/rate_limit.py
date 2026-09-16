"""Rate limiting for the two unauthenticated POST license routes.

Two buckets per request -- one on the caller's IP, one on the folded email --
over the existing Redis token bucket, which already degrades to per-process
memory during a Redis outage rather than failing closed.

These also protect the Keygen tier quota: one resend is N check-out calls.
"""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from app.config import config
from app.gateway.ratelimit import acquire_token
from app.rate_limiter import get_real_client_ip

from .email.address import fold_email

_SECONDS_PER_HOUR = 3600.0

_EMAIL_LIMITS = {
    "resend": lambda: config.LICENSE_RESEND_RATE_LIMIT_PER_HOUR,
    "trial": lambda: config.LICENSE_TRIAL_RATE_LIMIT_PER_HOUR,
}


async def _consume(scope: str, per_hour: int) -> bool:
    if per_hour <= 0:
        return True
    wait_ms = await acquire_token(
        scope,
        capacity=per_hour,
        refill_per_sec=per_hour / _SECONDS_PER_HOUR,
    )
    return wait_ms == 0


async def enforce_license_rate_limit(
    request: Request,
    *,
    route: str,
    email: str,
) -> None:
    """Raise 429 when either bucket is empty."""
    ip = get_real_client_ip(request)
    ip_ok = await _consume(
        f"license:{route}:ip:{ip}", config.LICENSE_RATE_LIMIT_IP_PER_HOUR
    )
    email_ok = await _consume(
        f"license:{route}:email:{fold_email(email)}", _EMAIL_LIMITS[route]()
    )
    if not (ip_ok and email_ok):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Try again later.",
        )
