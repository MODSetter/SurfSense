"""
Atomic token quota service for anonymous and registered users.

Provides reserve/finalize/release/get_usage operations with race-safe
implementation using Redis Lua scripts (anonymous) and Postgres row locks
(registered premium).
"""

from __future__ import annotations

import hashlib
import logging
from enum import StrEnum
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config

logger = logging.getLogger(__name__)


class QuotaScope(StrEnum):
    ANONYMOUS = "anonymous"
    PREMIUM = "premium"


class QuotaStatus(StrEnum):
    OK = "ok"
    WARNING = "warning"
    BLOCKED = "blocked"


class QuotaResult:
    __slots__ = ("allowed", "limit", "remaining", "reserved", "status", "used")

    def __init__(
        self,
        allowed: bool,
        status: QuotaStatus,
        used: int,
        limit: int,
        reserved: int = 0,
        remaining: int = 0,
    ):
        self.allowed = allowed
        self.status = status
        self.used = used
        self.limit = limit
        self.reserved = reserved
        self.remaining = remaining

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "status": self.status.value,
            "used": self.used,
            "limit": self.limit,
            "reserved": self.reserved,
            "remaining": self.remaining,
        }


# ---------------------------------------------------------------------------
# Redis Lua scripts for atomic anonymous quota operations
# ---------------------------------------------------------------------------

# KEYS[1] = quota key (e.g. "anon_quota:session:<session_id>")
# ARGV[1] = reserve_tokens
# ARGV[2] = limit
# ARGV[3] = warning_threshold
# ARGV[4] = request_id
# ARGV[5] = ttl_seconds
# Returns: [allowed(0/1), status("ok"/"warning"/"blocked"), used, reserved]
_RESERVE_LUA = """
local key = KEYS[1]
local reserve = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local warning = tonumber(ARGV[3])
local req_id = ARGV[4]
local ttl = tonumber(ARGV[5])

local used = tonumber(redis.call('HGET', key, 'used') or '0')
local reserved = tonumber(redis.call('HGET', key, 'reserved') or '0')

local effective = used + reserved + reserve
if effective > limit then
    return {0, 'blocked', used, reserved}
end

redis.call('HINCRBY', key, 'reserved', reserve)
redis.call('HSET', key, 'req:' .. req_id, reserve)
redis.call('EXPIRE', key, ttl)

local new_reserved = reserved + reserve
local status = 'ok'
if (used + new_reserved) >= warning then
    status = 'warning'
end

return {1, status, used, new_reserved}
"""

# KEYS[1] = quota key
# ARGV[1] = request_id
# ARGV[2] = actual_tokens
# ARGV[3] = warning_threshold
# Returns: [used, reserved, status]
_FINALIZE_LUA = """
local key = KEYS[1]
local req_id = ARGV[1]
local actual = tonumber(ARGV[2])
local warning = tonumber(ARGV[3])

local orig_reserve = tonumber(redis.call('HGET', key, 'req:' .. req_id) or '0')
if orig_reserve == 0 then
    return {tonumber(redis.call('HGET', key, 'used') or '0'), tonumber(redis.call('HGET', key, 'reserved') or '0'), 'ok'}
end

redis.call('HDEL', key, 'req:' .. req_id)
redis.call('HINCRBY', key, 'reserved', -orig_reserve)
redis.call('HINCRBY', key, 'used', actual)

local used = tonumber(redis.call('HGET', key, 'used') or '0')
local reserved = tonumber(redis.call('HGET', key, 'reserved') or '0')
local status = 'ok'
if used >= warning then
    status = 'warning'
end
return {used, reserved, status}
"""

# KEYS[1] = quota key
# ARGV[1] = request_id
# Returns: 1 if released, 0 if not found
_RELEASE_LUA = """
local key = KEYS[1]
local req_id = ARGV[1]

local orig_reserve = tonumber(redis.call('HGET', key, 'req:' .. req_id) or '0')
if orig_reserve == 0 then
    return 0
end

redis.call('HDEL', key, 'req:' .. req_id)
redis.call('HINCRBY', key, 'reserved', -orig_reserve)
return 1
"""


def _get_anon_redis() -> aioredis.Redis:
    return aioredis.from_url(config.REDIS_APP_URL, decode_responses=True)


def compute_anon_identity_key(
    session_id: str,
    ip_hash: str | None = None,
) -> str:
    """Build the Redis hash key for anonymous quota tracking.

    Uses the signed session cookie as primary identity. The IP hash
    is tracked separately so cookie-reset evasion is caught.
    """
    return f"anon_quota:session:{session_id}"


def compute_ip_quota_key(ip_address: str) -> str:
    """Build IP-only quota key. UA is excluded so rotating User-Agent cannot bypass limits."""
    h = hashlib.sha256(ip_address.encode()).hexdigest()[:16]
    return f"anon_quota:ip:{h}"


# ---------------------------------------------------------------------------
# Concurrent stream limiter (per-IP)
# ---------------------------------------------------------------------------

# Atomic acquire: returns 1 if slot acquired, 0 if at capacity.
# KEYS[1] = stream counter key   ARGV[1] = max_concurrent   ARGV[2] = safety_ttl
_ACQUIRE_STREAM_LUA = """
local key = KEYS[1]
local max_c = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])
local cur = tonumber(redis.call('GET', key) or '0')
if cur >= max_c then
    return 0
end
redis.call('INCR', key)
redis.call('EXPIRE', key, ttl)
return 1
"""

# Atomic release: DECR with floor at 0
_RELEASE_STREAM_LUA = """
local key = KEYS[1]
local cur = tonumber(redis.call('GET', key) or '0')
if cur <= 0 then
    return 0
end
redis.call('DECR', key)
return 1
"""


def compute_stream_slot_key(ip_address: str) -> str:
    h = hashlib.sha256(ip_address.encode()).hexdigest()[:16]
    return f"anon:streams:{h}"


def compute_request_count_key(ip_address: str) -> str:
    h = hashlib.sha256(ip_address.encode()).hexdigest()[:16]
    return f"anon:reqcount:{h}"


class TokenQuotaService:
    """Unified quota service for anonymous (Redis) and premium (Postgres) scopes."""

    # ------------------------------------------------------------------
    # Concurrent stream limiter
    # ------------------------------------------------------------------

    @staticmethod
    async def anon_acquire_stream_slot(
        ip_address: str,
        max_concurrent: int = 2,
        safety_ttl: int = 300,
    ) -> bool:
        key = compute_stream_slot_key(ip_address)
        r = _get_anon_redis()
        try:
            result = await r.eval(
                _ACQUIRE_STREAM_LUA, 1, key, str(max_concurrent), str(safety_ttl)
            )
            return bool(result)
        finally:
            await r.aclose()

    @staticmethod
    async def anon_release_stream_slot(ip_address: str) -> None:
        key = compute_stream_slot_key(ip_address)
        r = _get_anon_redis()
        try:
            await r.eval(_RELEASE_STREAM_LUA, 1, key)
        finally:
            await r.aclose()

    # ------------------------------------------------------------------
    # Per-IP request counter (for CAPTCHA triggering)
    # ------------------------------------------------------------------

    @staticmethod
    async def anon_increment_request_count(ip_address: str, ttl: int = 86400) -> int:
        """Increment and return current request count for this IP. TTL resets daily."""
        key = compute_request_count_key(ip_address)
        r = _get_anon_redis()
        try:
            pipe = r.pipeline()
            pipe.incr(key)
            pipe.expire(key, ttl)
            results = await pipe.execute()
            return int(results[0])
        finally:
            await r.aclose()

    @staticmethod
    async def anon_get_request_count(ip_address: str) -> int:
        key = compute_request_count_key(ip_address)
        r = _get_anon_redis()
        try:
            val = await r.get(key)
            return int(val) if val else 0
        finally:
            await r.aclose()

    @staticmethod
    async def anon_reset_request_count(ip_address: str) -> None:
        key = compute_request_count_key(ip_address)
        r = _get_anon_redis()
        try:
            await r.delete(key)
        finally:
            await r.aclose()

    # ------------------------------------------------------------------
    # Anonymous (Redis-backed)
    # ------------------------------------------------------------------

    @staticmethod
    async def anon_reserve(
        session_key: str,
        ip_key: str | None,
        request_id: str,
        reserve_tokens: int,
    ) -> QuotaResult:
        limit = config.ANON_TOKEN_LIMIT
        warning = config.ANON_TOKEN_WARNING_THRESHOLD
        ttl = config.ANON_TOKEN_QUOTA_TTL_DAYS * 86400

        r = _get_anon_redis()
        try:
            result = await r.eval(
                _RESERVE_LUA,
                1,
                session_key,
                str(reserve_tokens),
                str(limit),
                str(warning),
                request_id,
                str(ttl),
            )
            allowed = bool(result[0])
            status_str = result[1] if isinstance(result[1], str) else result[1].decode()
            used = int(result[2])
            reserved = int(result[3])

            if ip_key:
                ip_result = await r.eval(
                    _RESERVE_LUA,
                    1,
                    ip_key,
                    str(reserve_tokens),
                    str(limit),
                    str(warning),
                    request_id,
                    str(ttl),
                )
                ip_allowed = bool(ip_result[0])
                ip_used = int(ip_result[2])
                if not ip_allowed and allowed:
                    await r.eval(_RELEASE_LUA, 1, session_key, request_id)
                    allowed = False
                    status_str = "blocked"
                    used = max(used, ip_used)

            status = QuotaStatus(status_str)
            remaining = max(0, limit - used - reserved)
            return QuotaResult(
                allowed=allowed,
                status=status,
                used=used,
                limit=limit,
                reserved=reserved,
                remaining=remaining,
            )
        finally:
            await r.aclose()

    @staticmethod
    async def anon_finalize(
        session_key: str,
        ip_key: str | None,
        request_id: str,
        actual_tokens: int,
    ) -> QuotaResult:
        warning = config.ANON_TOKEN_WARNING_THRESHOLD
        limit = config.ANON_TOKEN_LIMIT
        r = _get_anon_redis()
        try:
            result = await r.eval(
                _FINALIZE_LUA,
                1,
                session_key,
                request_id,
                str(actual_tokens),
                str(warning),
            )
            used = int(result[0])
            reserved = int(result[1])
            status_str = result[2] if isinstance(result[2], str) else result[2].decode()

            if ip_key:
                await r.eval(
                    _FINALIZE_LUA,
                    1,
                    ip_key,
                    request_id,
                    str(actual_tokens),
                    str(warning),
                )

            status = QuotaStatus(status_str)
            remaining = max(0, limit - used - reserved)
            return QuotaResult(
                allowed=True,
                status=status,
                used=used,
                limit=limit,
                reserved=reserved,
                remaining=remaining,
            )
        finally:
            await r.aclose()

    @staticmethod
    async def anon_release(
        session_key: str,
        ip_key: str | None,
        request_id: str,
    ) -> None:
        r = _get_anon_redis()
        try:
            await r.eval(_RELEASE_LUA, 1, session_key, request_id)
            if ip_key:
                await r.eval(_RELEASE_LUA, 1, ip_key, request_id)
        finally:
            await r.aclose()

    @staticmethod
    async def anon_get_usage(session_key: str) -> QuotaResult:
        limit = config.ANON_TOKEN_LIMIT
        warning = config.ANON_TOKEN_WARNING_THRESHOLD
        r = _get_anon_redis()
        try:
            data = await r.hgetall(session_key)
            used = int(data.get("used", 0))
            reserved = int(data.get("reserved", 0))
            remaining = max(0, limit - used - reserved)

            if used >= limit:
                status = QuotaStatus.BLOCKED
            elif used >= warning:
                status = QuotaStatus.WARNING
            else:
                status = QuotaStatus.OK

            return QuotaResult(
                allowed=used < limit,
                status=status,
                used=used,
                limit=limit,
                reserved=reserved,
                remaining=remaining,
            )
        finally:
            await r.aclose()

    # ------------------------------------------------------------------
    # Premium (Postgres-backed)
    # ------------------------------------------------------------------

    @staticmethod
    async def premium_reserve(
        db_session: AsyncSession,
        user_id: Any,
        request_id: str,
        reserve_tokens: int,
    ) -> QuotaResult:
        from app.db import User

        user = (
            (
                await db_session.execute(
                    select(User).where(User.id == user_id).with_for_update(of=User)
                )
            )
            .unique()
            .scalar_one_or_none()
        )
        if user is None:
            return QuotaResult(
                allowed=False,
                status=QuotaStatus.BLOCKED,
                used=0,
                limit=0,
            )

        limit = user.premium_tokens_limit
        used = user.premium_tokens_used
        reserved = user.premium_tokens_reserved

        effective = used + reserved + reserve_tokens
        if effective > limit:
            remaining = max(0, limit - used - reserved)
            await db_session.rollback()
            return QuotaResult(
                allowed=False,
                status=QuotaStatus.BLOCKED,
                used=used,
                limit=limit,
                reserved=reserved,
                remaining=remaining,
            )

        user.premium_tokens_reserved = reserved + reserve_tokens
        await db_session.commit()

        new_reserved = reserved + reserve_tokens
        remaining = max(0, limit - used - new_reserved)
        warning_threshold = int(limit * 0.8)

        if (used + new_reserved) >= limit:
            status = QuotaStatus.BLOCKED
        elif (used + new_reserved) >= warning_threshold:
            status = QuotaStatus.WARNING
        else:
            status = QuotaStatus.OK

        return QuotaResult(
            allowed=True,
            status=status,
            used=used,
            limit=limit,
            reserved=new_reserved,
            remaining=remaining,
        )

    @staticmethod
    async def premium_finalize(
        db_session: AsyncSession,
        user_id: Any,
        request_id: str,
        actual_tokens: int,
        reserved_tokens: int,
    ) -> QuotaResult:
        from app.db import User

        user = (
            (
                await db_session.execute(
                    select(User).where(User.id == user_id).with_for_update(of=User)
                )
            )
            .unique()
            .scalar_one_or_none()
        )
        if user is None:
            return QuotaResult(
                allowed=False, status=QuotaStatus.BLOCKED, used=0, limit=0
            )

        user.premium_tokens_reserved = max(
            0, user.premium_tokens_reserved - reserved_tokens
        )
        user.premium_tokens_used = user.premium_tokens_used + actual_tokens

        await db_session.commit()

        limit = user.premium_tokens_limit
        used = user.premium_tokens_used
        reserved = user.premium_tokens_reserved
        remaining = max(0, limit - used - reserved)

        warning_threshold = int(limit * 0.8)
        if used >= limit:
            status = QuotaStatus.BLOCKED
        elif used >= warning_threshold:
            status = QuotaStatus.WARNING
        else:
            status = QuotaStatus.OK

        return QuotaResult(
            allowed=True,
            status=status,
            used=used,
            limit=limit,
            reserved=reserved,
            remaining=remaining,
        )

    @staticmethod
    async def premium_release(
        db_session: AsyncSession,
        user_id: Any,
        reserved_tokens: int,
    ) -> None:
        from app.db import User

        user = (
            (
                await db_session.execute(
                    select(User).where(User.id == user_id).with_for_update(of=User)
                )
            )
            .unique()
            .scalar_one_or_none()
        )
        if user is not None:
            user.premium_tokens_reserved = max(
                0, user.premium_tokens_reserved - reserved_tokens
            )
            await db_session.commit()

    @staticmethod
    async def premium_get_usage(
        db_session: AsyncSession,
        user_id: Any,
    ) -> QuotaResult:
        from app.db import User

        user = (
            (await db_session.execute(select(User).where(User.id == user_id)))
            .unique()
            .scalar_one_or_none()
        )
        if user is None:
            return QuotaResult(
                allowed=False, status=QuotaStatus.BLOCKED, used=0, limit=0
            )

        limit = user.premium_tokens_limit
        used = user.premium_tokens_used
        reserved = user.premium_tokens_reserved
        remaining = max(0, limit - used - reserved)

        warning_threshold = int(limit * 0.8)
        if used >= limit:
            status = QuotaStatus.BLOCKED
        elif used >= warning_threshold:
            status = QuotaStatus.WARNING
        else:
            status = QuotaStatus.OK

        return QuotaResult(
            allowed=used < limit,
            status=status,
            used=used,
            limit=limit,
            reserved=reserved,
            remaining=remaining,
        )
