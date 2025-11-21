"""
FastAPI dependencies for rate limiting checks.

This module provides reusable dependencies for checking rate limits
across different endpoints to avoid code duplication.
"""

import ipaddress
import logging
import os
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.services.rate_limit_service import RateLimitService
from app.services.security_event_service import SecurityEventService

logger = logging.getLogger(__name__)

# Trusted proxy configuration
# In production, set TRUSTED_PROXIES env var to comma-separated list of proxy IPs
TRUSTED_PROXIES = set(
    filter(None, os.getenv("TRUSTED_PROXIES", "").split(","))
)


def is_valid_ip(ip_str: str) -> bool:
    """
    Validate if a string is a valid IP address.

    Args:
        ip_str: String to validate

    Returns:
        True if valid IPv4 or IPv6 address, False otherwise
    """
    if not ip_str:
        return False

    try:
        ipaddress.ip_address(ip_str.strip())
        return True
    except ValueError:
        return False


def get_client_ip(request: Request) -> str | None:
    """
    Extract the real client IP address from the request.

    Handles reverse proxy scenarios by checking proxy headers in order:
    1. X-Forwarded-For (first IP in the list, closest to client)
    2. X-Real-IP (set by some proxies)
    3. request.client.host (direct connection)

    Security Features:
    - Validates all IP addresses before returning
    - Only trusts proxy headers from configured trusted proxies
    - Falls back through chain if IPs are invalid

    Args:
        request: The FastAPI request object

    Returns:
        Valid IP address if available, None otherwise

    Note:
        In production behind a reverse proxy (Nginx, Cloudflare, etc.),
        this properly identifies individual users instead of treating all
        requests as coming from the proxy IP.

        Set TRUSTED_PROXIES environment variable to enable proxy header validation:
        TRUSTED_PROXIES=10.0.0.1,172.16.0.1
    """
    # Get the immediate client IP (could be proxy or end user)
    immediate_client = request.client.host if request.client else None

    # Check if we should trust proxy headers
    # Only trust headers if immediate client is a known proxy
    trust_proxy_headers = False
    if TRUSTED_PROXIES and immediate_client:
        trust_proxy_headers = immediate_client in TRUSTED_PROXIES
    elif not TRUSTED_PROXIES:
        # If no trusted proxies configured, trust all headers (backward compatible)
        # In production, TRUSTED_PROXIES should always be set for security
        trust_proxy_headers = True

    # Check X-Forwarded-For header (used by most reverse proxies)
    # Format: "client, proxy1, proxy2" - we want the first (client) IP
    if trust_proxy_headers and "x-forwarded-for" in request.headers:
        forwarded_for = request.headers["x-forwarded-for"]
        # Get the first IP in the chain (the original client)
        client_ip = forwarded_for.split(",")[0].strip()
        if is_valid_ip(client_ip):
            return client_ip
        else:
            logger.warning(
                f"Invalid IP in X-Forwarded-For header: {client_ip}. "
                f"Falling back to next method."
            )

    # Check X-Real-IP header (used by some proxies like Nginx)
    if trust_proxy_headers and "x-real-ip" in request.headers:
        real_ip = request.headers["x-real-ip"].strip()
        if is_valid_ip(real_ip):
            return real_ip
        else:
            logger.warning(
                f"Invalid IP in X-Real-IP header: {real_ip}. "
                f"Falling back to direct client."
            )

    # Fall back to direct client connection
    if immediate_client and is_valid_ip(immediate_client):
        return immediate_client

    # No valid IP found
    logger.warning("No valid client IP address could be determined")
    return None


async def check_rate_limit(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> str | None:
    """
    Dependency to check if the requesting IP is rate limited.

    This dependency:
    - Extracts the real client IP (handling reverse proxies)
    - Validates IP address format
    - Checks if the IP is currently blocked
    - Logs rate limit hits to security events for monitoring
    - Raises 429 Too Many Requests if blocked
    - Returns the IP address for use in the endpoint

    Security Note:
    - Error messages are intentionally vague to prevent timing attacks
    - Retry-After header rounds to nearest minute to avoid precise timing info
    - Logs structured data for security monitoring and attack pattern analysis

    Args:
        request: The FastAPI request object
        session: Database session for logging

    Returns:
        IP address if available, None otherwise

    Raises:
        HTTPException: 429 Too Many Requests if IP is blocked

    Example:
        ```python
        @router.post("/endpoint")
        async def my_endpoint(ip_address: str | None = Depends(check_rate_limit)):
            # IP address is available here if not None
            # Endpoint proceeds only if not rate limited
            pass
        ```
    """
    # Extract the real client IP address
    ip_address = get_client_ip(request)

    # Check if IP is blocked
    if ip_address:
        is_blocked, block_info = RateLimitService.is_ip_blocked(ip_address)
        if is_blocked and block_info:
            # Round remaining time to nearest minute to avoid precise timing info
            # This prevents attackers from using exact timing to optimize brute force
            remaining_minutes = max(1, (block_info.remaining_seconds + 30) // 60)

            # Log the rate limit hit for security monitoring
            # This helps identify persistent attackers and attack patterns
            user_agent = request.headers.get("user-agent")
            endpoint = str(request.url.path)

            # Use the user_id from the block_info if available, otherwise use a sentinel value
            # Note: Some rate limit hits occur before authentication, so user may not be known
            user_id = block_info.user_id if block_info.user_id else "00000000-0000-0000-0000-000000000000"

            try:
                await SecurityEventService.log_rate_limit_hit(
                    session=session,
                    user_id=user_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    details={
                        "endpoint": endpoint,
                        "remaining_seconds": block_info.remaining_seconds,
                        "failed_attempts": block_info.failed_attempts,
                        "reason": block_info.reason,
                        "lockout_type": block_info.lockout_type,
                    },
                )
            except Exception:
                # Don't let logging failures prevent rate limiting from working
                logger.exception(
                    f"Failed to log rate limit hit for IP {ip_address} "
                    f"accessing {endpoint}"
                )

            # Structured logging for monitoring and alerting
            logger.warning(
                f"Rate limit hit: IP {ip_address} blocked from accessing {endpoint}. "
                f"Attempts: {block_info.failed_attempts}, "
                f"Remaining: {block_info.remaining_seconds}s, "
                f"Reason: {block_info.reason}"
            )

            raise HTTPException(
                status_code=429,
                detail="Too many failed attempts. Please try again later.",
                headers={"Retry-After": str(remaining_minutes * 60)},
            )

    return ip_address
