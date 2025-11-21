"""
FastAPI dependencies for rate limiting checks.

This module provides reusable dependencies for checking rate limits
across different endpoints to avoid code duplication.
"""

from fastapi import HTTPException, Request

from app.services.rate_limit_service import RateLimitService


async def check_rate_limit(request: Request) -> str | None:
    """
    Dependency to check if the requesting IP is rate limited.

    Args:
        request: The FastAPI request object

    Returns:
        IP address if available, None otherwise

    Raises:
        HTTPException: 429 Too Many Requests if IP is blocked
    """
    # Extract IP address from request
    ip_address = None
    if request.client:
        ip_address = request.client.host

    # Check if IP is blocked
    if ip_address:
        is_blocked, block_info = RateLimitService.is_ip_blocked(ip_address)
        if is_blocked and block_info:
            raise HTTPException(
                status_code=429,
                detail=f"Too many failed attempts. Please try again in {block_info.remaining_seconds} seconds.",
                headers={"Retry-After": str(block_info.remaining_seconds)},
            )

    return ip_address
