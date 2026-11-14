"""Rate limiting for the unauthenticated POST license routes.

Two buckets per request, the caller's address first, then the folded email or,
for the app's refresh and its job packs, the key, over a Redis token bucket
that degrades to per-process memory during a Redis outage rather than failing
closed. A caller the address bucket refuses spends nothing of the other, so one
address cannot drain the key a firm's computers share.

These also protect the Keygen tier quota: one resend is N check-out calls.
"""

from __future__ import annotations

import hashlib
from typing import NoReturn

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
    if not await _consume(
        f"license:{route}:ip:{ip}", config.LICENSE_RATE_LIMIT_IP_PER_HOUR
    ):
        _too_many()
    if not await _consume(
        f"license:{route}:email:{fold_email(email)}", _EMAIL_LIMITS[route]()
    ):
        _too_many()


async def _within_key_limits(
    request: Request, *, route: str, key: str, per_ip: int, per_key: int
) -> bool:
    """The address's bucket, then the key's, named by a hash of the key.

    The key is a bearer credential and must not sit in Redis or its logs.
    """
    if not await _consume(f"license:{route}:ip:{get_real_client_ip(request)}", per_ip):
        return False
    key_digest = hashlib.sha256(key.encode()).hexdigest()[:32]
    return await _consume(f"license:{route}:key:{key_digest}", per_key)


async def enforce_refresh_rate_limit(request: Request, *, key: str) -> None:
    """Raise 429 when the caller's or the key's bucket is empty."""
    if not await _within_key_limits(
        request,
        route="refresh",
        key=key,
        per_ip=config.LICENSE_REFRESH_RATE_LIMIT_IP_PER_HOUR,
        per_key=config.LICENSE_REFRESH_RATE_LIMIT_PER_HOUR,
    ):
        _too_many()


async def enforce_job_pack_rate_limit(request: Request, *, key: str) -> None:
    """Raise 429 `rate_limited`, contract 6's refusal, when either bucket is empty."""
    if not await _within_key_limits(
        request,
        route="job-pack",
        key=key,
        per_ip=config.LICENSE_JOB_PACK_RATE_LIMIT_IP_PER_HOUR,
        per_key=config.LICENSE_JOB_PACK_RATE_LIMIT_PER_HOUR,
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "rate_limited",
                "message": "Too many requests. Try again later.",
            },
        )


def _too_many() -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many requests. Try again later.",
    )
