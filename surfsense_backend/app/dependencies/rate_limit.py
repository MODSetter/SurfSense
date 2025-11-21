"""
FastAPI dependencies for rate limiting checks.

This module provides reusable dependencies for checking rate limits
across different endpoints to avoid code duplication.
"""

from fastapi import HTTPException, Request

from app.services.rate_limit_service import RateLimitService


def get_client_ip(request: Request) -> str | None:
    """
    Extract the real client IP address from the request.

    Handles reverse proxy scenarios by checking proxy headers in order:
    1. X-Forwarded-For (first IP in the list, closest to client)
    2. X-Real-IP (set by some proxies)
    3. request.client.host (direct connection)

    Args:
        request: The FastAPI request object

    Returns:
        IP address if available, None otherwise

    Note:
        In production behind a reverse proxy (Nginx, Cloudflare, etc.),
        this properly identifies individual users instead of treating all
        requests as coming from the proxy IP.
    """
    # Check X-Forwarded-For header (used by most reverse proxies)
    # Format: "client, proxy1, proxy2" - we want the first (client) IP
    if "x-forwarded-for" in request.headers:
        forwarded_for = request.headers["x-forwarded-for"]
        # Get the first IP in the chain (the original client)
        return forwarded_for.split(",")[0].strip()

    # Check X-Real-IP header (used by some proxies like Nginx)
    if "x-real-ip" in request.headers:
        return request.headers["x-real-ip"]

    # Fall back to direct client connection
    if request.client:
        return request.client.host

    return None


async def check_rate_limit(request: Request) -> str | None:
    """
    Dependency to check if the requesting IP is rate limited.

    This dependency:
    - Extracts the real client IP (handling reverse proxies)
    - Checks if the IP is currently blocked
    - Raises 429 Too Many Requests if blocked
    - Returns the IP address for use in the endpoint

    Args:
        request: The FastAPI request object

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
            raise HTTPException(
                status_code=429,
                detail=f"Too many failed attempts. Please try again in {block_info.remaining_seconds} seconds.",
                headers={"Retry-After": str(block_info.remaining_seconds)},
            )

    return ip_address
