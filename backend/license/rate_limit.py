"""Rate limiting for the unauthenticated POST license routes.

Two buckets per request -- one on the caller's IP, one on the folded email or,
for the app's refresh, on the key -- over a Redis token bucket, which degrades
to per-process memory during a Redis outage rather than failing closed.

These also protect the Keygen tier quota: one resend is N check-out calls.
"""

from __future__ import annotations

import hashlib

from fastapi import HTTPException, Request, status

from license.client_ip import get_real_client_ip
from license.settings import config
from license.token_bucket import acquire_token

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
        _too_many()


async def enforce_refresh_rate_limit(request: Request, *, key: str) -> None:
    """Raise 429 when the caller's or the key's bucket is empty.

    The bucket is named by a hash of the key: the key is a bearer credential
    and must not sit in Redis or its logs.
    """
    ip = get_real_client_ip(request)
    key_digest = hashlib.sha256(key.encode()).hexdigest()[:32]
    ip_ok = await _consume(
        f"license:refresh:ip:{ip}", config.LICENSE_REFRESH_RATE_LIMIT_IP_PER_HOUR
    )
    key_ok = await _consume(
        f"license:refresh:key:{key_digest}", config.LICENSE_REFRESH_RATE_LIMIT_PER_HOUR
    )
    if not (ip_ok and key_ok):
        _too_many()


def _too_many() -> None:
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many requests. Try again later.",
    )
