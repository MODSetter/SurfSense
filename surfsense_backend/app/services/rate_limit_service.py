"""
Rate limiting service for managing IP blocks and failed login attempts.

This service tracks failed authentication attempts and automatically blocks
IP addresses that exceed thresholds. It also provides functionality for
administrators to view and manually unlock blocked IPs.
"""

import json
import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import redis
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Redis configuration
REDIS_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
_redis_client: redis.Redis | None = None

# Redis key prefixes
RATE_LIMIT_PREFIX = "rate_limit:"
BLOCKED_IP_PREFIX = f"{RATE_LIMIT_PREFIX}blocked_ip:"
FAILED_ATTEMPTS_PREFIX = f"{RATE_LIMIT_PREFIX}failed_attempts:"
BLOCKED_IPS_SET = f"{RATE_LIMIT_PREFIX}blocked_ips"

# Rate limiting configuration
MAX_FAILED_ATTEMPTS = int(os.getenv("RATE_LIMIT_MAX_ATTEMPTS", "5"))
LOCKOUT_DURATION_MINUTES = int(os.getenv("RATE_LIMIT_LOCKOUT_MINUTES", "60"))
ATTEMPT_WINDOW_MINUTES = int(os.getenv("RATE_LIMIT_WINDOW_MINUTES", "15"))


class BlockedIP(BaseModel):
    """Model representing a blocked IP address."""

    ip_address: str
    user_id: str | None
    username: str | None
    blocked_at: datetime
    expires_at: datetime
    remaining_seconds: int
    failed_attempts: int
    reason: str
    lockout_type: str = "temporary"


class RateLimitStats(BaseModel):
    """Statistics about rate limiting and blocked IPs."""

    active_blocks: int
    blocks_24h: int
    blocks_7d: int
    avg_lockout_duration: int


def get_redis_client() -> redis.Redis:
    """Get or create Redis client for rate limiting."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


class RateLimitService:
    """Service for managing rate limiting and IP blocks."""

    @staticmethod
    def record_failed_attempt(
        ip_address: str,
        user_id: str | None = None,
        username: str | None = None,
        reason: str = "exceeded_max_attempts",
    ) -> tuple[bool, int]:
        """
        Record a failed authentication attempt for an IP address.

        Returns:
            Tuple of (should_block, attempt_count)
        """
        try:
            client = get_redis_client()
            attempts_key = f"{FAILED_ATTEMPTS_PREFIX}{ip_address}"

            # Use pipeline to make INCR and EXPIRE atomic
            pipe = client.pipeline()
            pipe.incr(attempts_key)
            pipe.expire(attempts_key, ATTEMPT_WINDOW_MINUTES * 60)
            results = pipe.execute()
            attempts = results[0]

            # Check if should block
            if attempts >= MAX_FAILED_ATTEMPTS:
                RateLimitService.block_ip(
                    ip_address=ip_address,
                    user_id=user_id,
                    username=username,
                    failed_attempts=attempts,
                    reason=reason,
                )
                return True, attempts

            return False, attempts

        except redis.RedisError as e:
            logger.error(f"Failed to record failed attempt in Redis: {e}")
            return False, 0

    @staticmethod
    def block_ip(
        ip_address: str,
        user_id: str | None = None,
        username: str | None = None,
        failed_attempts: int = MAX_FAILED_ATTEMPTS,
        reason: str = "exceeded_max_attempts",
        duration_minutes: int = LOCKOUT_DURATION_MINUTES,
    ) -> bool:
        """
        Block an IP address for a specified duration.

        Args:
            ip_address: IP address to block
            user_id: Optional user ID associated with attempts
            username: Optional username that was targeted
            failed_attempts: Number of failed attempts that triggered the block
            reason: Reason for blocking
            duration_minutes: Duration of the block in minutes

        Returns:
            True if successfully blocked, False otherwise
        """
        try:
            client = get_redis_client()
            blocked_at = datetime.now(UTC)
            expires_at = blocked_at + timedelta(minutes=duration_minutes)

            # Store block details
            block_data = {
                "ip_address": ip_address,
                "user_id": user_id or "",
                "username": username or "Unknown",
                "blocked_at": blocked_at.isoformat(),
                "expires_at": expires_at.isoformat(),
                "failed_attempts": failed_attempts,
                "reason": reason,
                "lockout_type": "temporary",
            }

            block_key = f"{BLOCKED_IP_PREFIX}{ip_address}"
            client.setex(
                block_key,
                duration_minutes * 60,
                json.dumps(block_data),
            )

            # Add to sorted set for easy querying (score = expiry timestamp)
            client.zadd(
                BLOCKED_IPS_SET,
                {ip_address: expires_at.timestamp()},
            )

            logger.info(
                f"Blocked IP {ip_address} for {duration_minutes} minutes "
                f"(user: {username or 'Unknown'}, attempts: {failed_attempts})"
            )

            return True

        except redis.RedisError as e:
            logger.error(f"Failed to block IP in Redis: {e}")
            return False

    @staticmethod
    def is_ip_blocked(ip_address: str) -> tuple[bool, BlockedIP | None]:
        """
        Check if an IP address is currently blocked.

        Returns:
            Tuple of (is_blocked, block_details)
        """
        try:
            client = get_redis_client()
            block_key = f"{BLOCKED_IP_PREFIX}{ip_address}"
            block_data = client.get(block_key)

            if not block_data:
                return False, None

            data = json.loads(block_data)
            blocked_at = datetime.fromisoformat(data["blocked_at"])
            expires_at = datetime.fromisoformat(data["expires_at"])
            now = datetime.now(UTC)

            if now >= expires_at:
                # Block has expired, clean up
                RateLimitService._cleanup_expired_block(ip_address)
                return False, None

            remaining_seconds = int((expires_at - now).total_seconds())

            block = BlockedIP(
                ip_address=ip_address,
                user_id=data.get("user_id") or None,
                username=data.get("username", "Unknown"),
                blocked_at=blocked_at,
                expires_at=expires_at,
                remaining_seconds=remaining_seconds,
                failed_attempts=data.get("failed_attempts", 0),
                reason=data.get("reason", "exceeded_max_attempts"),
                lockout_type=data.get("lockout_type", "temporary"),
            )

            return True, block

        except (redis.RedisError, json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to check if IP is blocked: {e}")
            return False, None

    @staticmethod
    def get_all_blocked_ips() -> list[BlockedIP]:
        """
        Get all currently blocked IP addresses.

        Returns:
            List of BlockedIP objects
        """
        try:
            client = get_redis_client()
            now = datetime.now(UTC)

            # Get all IPs from sorted set
            ip_addresses = client.zrangebyscore(
                BLOCKED_IPS_SET,
                now.timestamp(),
                "+inf",
            )

            if not ip_addresses:
                return []

            # Batch fetch all block data with mget to avoid N+1 queries
            block_keys = [f"{BLOCKED_IP_PREFIX}{ip}" for ip in ip_addresses]
            block_data_list = client.mget(block_keys)

            blocked_ips = []
            for ip_address, block_data in zip(ip_addresses, block_data_list):
                if not block_data:
                    continue

                try:
                    data = json.loads(block_data)
                    blocked_at = datetime.fromisoformat(data["blocked_at"])
                    expires_at = datetime.fromisoformat(data["expires_at"])

                    # Skip if expired
                    if now >= expires_at:
                        RateLimitService._cleanup_expired_block(ip_address)
                        continue

                    remaining_seconds = int((expires_at - now).total_seconds())

                    block = BlockedIP(
                        ip_address=ip_address,
                        user_id=data.get("user_id") or None,
                        username=data.get("username", "Unknown"),
                        blocked_at=blocked_at,
                        expires_at=expires_at,
                        remaining_seconds=remaining_seconds,
                        failed_attempts=data.get("failed_attempts", 0),
                        reason=data.get("reason", "exceeded_max_attempts"),
                        lockout_type=data.get("lockout_type", "temporary"),
                    )
                    blocked_ips.append(block)

                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    logger.warning(f"Invalid block data for IP {ip_address}: {e}")
                    continue

            # Sort by remaining time (descending)
            blocked_ips.sort(key=lambda x: x.remaining_seconds, reverse=True)

            return blocked_ips

        except redis.RedisError as e:
            logger.error(f"Failed to get blocked IPs from Redis: {e}")
            return []

    @staticmethod
    def unlock_ip(
        ip_address: str,
        admin_user_id: str | None = None,
        reason: str | None = None,
    ) -> bool:
        """
        Manually unlock an IP address (admin action).

        Args:
            ip_address: IP address to unlock
            admin_user_id: ID of admin performing the unlock
            reason: Optional reason for unlocking

        Returns:
            True if successfully unlocked, False otherwise
        """
        try:
            client = get_redis_client()

            # Remove block details
            block_key = f"{BLOCKED_IP_PREFIX}{ip_address}"
            client.delete(block_key)

            # Remove from sorted set
            client.zrem(BLOCKED_IPS_SET, ip_address)

            # Clear failed attempts counter
            attempts_key = f"{FAILED_ATTEMPTS_PREFIX}{ip_address}"
            client.delete(attempts_key)

            logger.info(
                f"IP {ip_address} unlocked by admin {admin_user_id or 'Unknown'} "
                f"(reason: {reason or 'Not specified'})"
            )

            return True

        except redis.RedisError as e:
            logger.error(f"Failed to unlock IP in Redis: {e}")
            return False

    @staticmethod
    def bulk_unlock_ips(
        ip_addresses: list[str],
        admin_user_id: str | None = None,
        reason: str | None = None,
    ) -> tuple[int, list[str]]:
        """
        Unlock multiple IP addresses at once.

        Args:
            ip_addresses: List of IP addresses to unlock
            admin_user_id: ID of admin performing the unlock
            reason: Optional reason for unlocking

        Returns:
            Tuple of (successful_count, failed_ips)
        """
        if not ip_addresses:
            return 0, []

        try:
            client = get_redis_client()

            # Use pipeline to batch all delete operations
            pipe = client.pipeline()

            # Queue all deletions
            for ip_address in ip_addresses:
                block_key = f"{BLOCKED_IP_PREFIX}{ip_address}"
                attempts_key = f"{FAILED_ATTEMPTS_PREFIX}{ip_address}"

                pipe.delete(block_key)
                pipe.delete(attempts_key)
                pipe.zrem(BLOCKED_IPS_SET, ip_address)

            # Execute all operations at once
            pipe.execute()

            logger.info(
                f"Bulk unlocked {len(ip_addresses)} IPs by admin {admin_user_id or 'Unknown'} "
                f"(reason: {reason or 'Not specified'})"
            )

            return len(ip_addresses), []

        except redis.RedisError as e:
            logger.error(
                f"Failed to bulk unlock {len(ip_addresses)} IPs in Redis: {e}. "
                f"All unlock operations failed."
            )
            # Return complete failure - if pipeline failed (likely connection issue),
            # individual operations would also fail, causing redundant error logs
            return 0, ip_addresses

    @staticmethod
    def get_statistics() -> RateLimitStats:
        """
        Get statistics about rate limiting.

        Returns:
            RateLimitStats object with current statistics
        """
        try:
            client = get_redis_client()
            now = datetime.now(UTC)

            # Active blocks
            active_blocks = client.zcount(
                BLOCKED_IPS_SET,
                now.timestamp(),
                "+inf",
            )

            # Note: Historical statistics (24h/7d) are not yet implemented
            # They require database storage. Setting to 0 to avoid misleading data.
            # To implement: Store block events in database with timestamps and query accordingly.
            blocks_24h = 0
            blocks_7d = 0

            return RateLimitStats(
                active_blocks=active_blocks,
                blocks_24h=blocks_24h,
                blocks_7d=blocks_7d,
                avg_lockout_duration=LOCKOUT_DURATION_MINUTES * 60,
            )

        except redis.RedisError as e:
            logger.error(f"Failed to get statistics from Redis: {e}")
            return RateLimitStats(
                active_blocks=0,
                blocks_24h=0,
                blocks_7d=0,
                avg_lockout_duration=LOCKOUT_DURATION_MINUTES * 60,
            )

    @staticmethod
    def _cleanup_expired_block(ip_address: str):
        """Clean up expired block from Redis."""
        try:
            client = get_redis_client()
            block_key = f"{BLOCKED_IP_PREFIX}{ip_address}"
            client.delete(block_key)
            client.zrem(BLOCKED_IPS_SET, ip_address)
        except redis.RedisError as e:
            logger.error(f"Failed to cleanup expired block: {e}")

    @staticmethod
    def cleanup_expired_blocks():
        """Remove all expired blocks from the sorted set."""
        try:
            client = get_redis_client()
            now = datetime.now(UTC)
            # Remove entries with score (expiry timestamp) less than now
            removed = client.zremrangebyscore(
                BLOCKED_IPS_SET,
                "-inf",
                now.timestamp(),
            )
            if removed > 0:
                logger.info(f"Cleaned up {removed} expired IP blocks")
        except redis.RedisError as e:
            logger.error(f"Failed to cleanup expired blocks: {e}")


# Create service instance
rate_limit_service = RateLimitService()
