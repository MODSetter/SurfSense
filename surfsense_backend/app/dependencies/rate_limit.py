"""
FastAPI dependencies for rate limiting checks.

This module provides reusable dependencies for checking rate limits
across different endpoints to avoid code duplication.
"""

from __future__ import annotations

import ipaddress
import logging
import os
from functools import lru_cache
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.services.rate_limit_service import RateLimitService
from app.services.security_event_service import SecurityEventService

logger = logging.getLogger(__name__)

# Trusted proxy configuration
# In production, set TRUSTED_PROXIES env var to comma-separated list of proxy IPs or CIDR ranges
# For Cloudflare, you can set CLOUDFLARE_PROXIES=true to automatically trust Cloudflare IPs


@lru_cache(maxsize=1)
def get_trusted_proxy_networks() -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    """
    Parse TRUSTED_PROXIES environment variable into IP network objects.

    Uses @lru_cache to parse only once and cache the result. Returns tuple for hashability.
    This design allows tests to mock this function rather than reloading the module.

    Supports both individual IPs and CIDR notation:
    - Single IP: "10.0.0.1"
    - CIDR range: "192.168.1.0/24"
    - Mixed: "10.0.0.1,192.168.1.0/24,172.16.0.0/16"

    Returns:
        Tuple of ip_network objects for trusted proxies (empty tuple if none configured)
    """
    proxies_str = os.getenv("TRUSTED_PROXIES", "")
    if not proxies_str:
        return ()

    networks = []
    for proxy in proxies_str.split(","):
        proxy = proxy.strip()
        if not proxy:
            continue

        try:
            # Try parsing as network (handles both single IPs and CIDR)
            # strict=False allows "192.168.1.1" to be treated as "192.168.1.1/32"
            network = ipaddress.ip_network(proxy, strict=False)
            networks.append(network)
        except ValueError as e:
            logger.warning(
                f"Invalid IP/CIDR in TRUSTED_PROXIES: '{proxy}' - {e}. Skipping."
            )
            continue

    return tuple(networks)

# Cloudflare IP ranges (updated as of January 2025)
# Source: https://www.cloudflare.com/ips-v4 and https://www.cloudflare.com/ips-v6
CLOUDFLARE_IPV4_RANGES = [
    "173.245.48.0/20",
    "103.21.244.0/22",
    "103.22.200.0/22",
    "103.31.4.0/22",
    "141.101.64.0/18",
    "108.162.192.0/18",
    "190.93.240.0/20",
    "188.114.96.0/20",
    "197.234.240.0/22",
    "198.41.128.0/17",
    "162.158.0.0/15",
    "104.16.0.0/13",
    "104.24.0.0/14",
    "172.64.0.0/13",
    "131.0.72.0/22",
]

CLOUDFLARE_IPV6_RANGES = [
    "2400:cb00::/32",
    "2606:4700::/32",
    "2803:f800::/32",
    "2405:b500::/32",
    "2405:8100::/32",
    "2a06:98c0::/29",
    "2c0f:f248::/32",
]

# Check if we should trust Cloudflare IPs
USE_CLOUDFLARE_PROXIES = os.getenv("CLOUDFLARE_PROXIES", "false").lower() == "true"


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


def is_ip_in_networks(
    ip_str: str, networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network]
) -> bool:
    """
    Check if an IP address is within any of the specified networks.

    Args:
        ip_str: IP address to check
        networks: List of IP networks to check against

    Returns:
        True if IP is in any of the networks, False otherwise
    """
    if not is_valid_ip(ip_str):
        return False

    try:
        ip_obj = ipaddress.ip_address(ip_str.strip())
        for network in networks:
            if ip_obj in network:
                return True
        return False
    except (ValueError, TypeError):
        return False


def is_trusted_proxy(ip_str: str) -> bool:
    """
    Check if an IP address is a trusted proxy.

    Trusted proxies are defined in TRUSTED_PROXIES environment variable
    and can be either individual IPs or CIDR ranges.

    Args:
        ip_str: IP address to check

    Returns:
        True if IP is a trusted proxy, False otherwise
    """
    trusted_networks = get_trusted_proxy_networks()
    if not trusted_networks:
        return False

    return is_ip_in_networks(ip_str, list(trusted_networks))


def is_cloudflare_ip(ip_str: str) -> bool:
    """
    Check if an IP address belongs to Cloudflare's network.

    Args:
        ip_str: IP address to check

    Returns:
        True if IP is from Cloudflare, False otherwise
    """
    if not is_valid_ip(ip_str):
        return False

    try:
        ip_obj = ipaddress.ip_address(ip_str.strip())

        # Check IPv4 ranges
        if isinstance(ip_obj, ipaddress.IPv4Address):
            for range_str in CLOUDFLARE_IPV4_RANGES:
                if ip_obj in ipaddress.ip_network(range_str):
                    return True

        # Check IPv6 ranges
        elif isinstance(ip_obj, ipaddress.IPv6Address):
            for range_str in CLOUDFLARE_IPV6_RANGES:
                if ip_obj in ipaddress.ip_network(range_str):
                    return True

        return False

    except (ValueError, TypeError):
        return False


def get_client_ip(request: Request) -> str | None:
    """
    Extract the real client IP address from the request.

    Handles reverse proxy scenarios by checking proxy headers in order:
    1. CF-Connecting-IP (Cloudflare's client IP header - most reliable for Cloudflare)
    2. X-Forwarded-For (first IP in the list, closest to client)
    3. X-Real-IP (set by some proxies like Nginx)
    4. request.client.host (direct connection)

    Security Features:
    - Validates all IP addresses before returning
    - Only trusts proxy headers from configured trusted proxies or Cloudflare
    - Falls back through chain if IPs are invalid
    - CF-Connecting-IP only trusted when request comes from Cloudflare

    Args:
        request: The FastAPI request object

    Returns:
        Valid IP address if available, None otherwise

    Security Warning:
        **CRITICAL**: This function trusts X-Forwarded-For, X-Real-IP, and CF-Connecting-IP
        headers ONLY from trusted proxies. Your reverse proxy MUST be configured to:

        1. Strip ALL incoming proxy headers from external clients
        2. Overwrite headers with the real client IP the proxy sees
        3. Block direct access to application (proxy-only access)

        Without proper proxy configuration, attackers can forge these headers to:
        - Bypass rate limiting by spoofing IPs
        - Launch DoS attacks by impersonating victim IPs
        - Evade security monitoring

        See SECURITY_IMPROVEMENTS.md for detailed proxy configuration requirements.

    Configuration:
        For Cloudflare deployments, set CLOUDFLARE_PROXIES=true:
        CLOUDFLARE_PROXIES=true

        For other reverse proxies, set TRUSTED_PROXIES:
        TRUSTED_PROXIES=10.0.0.1,172.16.0.1

        Or use CIDR ranges:
        TRUSTED_PROXIES=10.0.0.0/24,172.16.0.0/16
    """
    # Get the immediate client IP (could be proxy or end user)
    immediate_client = request.client.host if request.client else None

    # Determine if we should trust proxy headers
    trust_proxy_headers = False
    is_cloudflare_request = False

    # Check if request is from Cloudflare
    if USE_CLOUDFLARE_PROXIES and immediate_client:
        is_cloudflare_request = is_cloudflare_ip(immediate_client)
        trust_proxy_headers = is_cloudflare_request

    # Check if immediate client is in TRUSTED_PROXIES (supports CIDR ranges)
    trusted_networks = get_trusted_proxy_networks()
    if not trust_proxy_headers and trusted_networks and immediate_client:
        trust_proxy_headers = is_trusted_proxy(immediate_client)

    # Security: Do NOT trust proxy headers unless explicitly configured
    # If no TRUSTED_PROXIES or CLOUDFLARE_PROXIES are set, we use request.client.host
    # This prevents IP spoofing attacks where attackers forge X-Forwarded-For headers

    # Priority 1: CF-Connecting-IP (Cloudflare specific)
    # This is the most reliable header for Cloudflare as it cannot be spoofed
    if is_cloudflare_request and "cf-connecting-ip" in request.headers:
        cf_ip = request.headers["cf-connecting-ip"].strip()
        if is_valid_ip(cf_ip):
            logger.debug(f"Using CF-Connecting-IP: {cf_ip}")
            return cf_ip
        else:
            logger.warning(
                f"Invalid IP in CF-Connecting-IP header: {cf_ip}. "
                f"Falling back to next method."
            )

    # Priority 2: X-Forwarded-For (used by most reverse proxies)
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

    # Priority 3: X-Real-IP (used by some proxies like Nginx)
    if trust_proxy_headers and "x-real-ip" in request.headers:
        real_ip = request.headers["x-real-ip"].strip()
        if is_valid_ip(real_ip):
            return real_ip
        else:
            logger.warning(
                f"Invalid IP in X-Real-IP header: {real_ip}. "
                f"Falling back to direct client."
            )

    # Priority 4: Fall back to direct client connection
    if immediate_client and is_valid_ip(immediate_client):
        return immediate_client

    # No valid IP found
    logger.warning("No valid client IP address could be determined")
    return None


def get_cloudflare_metadata(request: Request) -> dict[str, str]:
    """
    Extract Cloudflare-specific metadata from request headers.

    Returns a dictionary with Cloudflare headers that are useful for
    security logging, debugging, and geo-blocking.

    Args:
        request: The FastAPI request object

    Returns:
        Dictionary with Cloudflare metadata (empty dict if no CF headers)
    """
    metadata = {}

    # CF-Ray: Unique request identifier across Cloudflare's network
    # Essential for correlating logs with Cloudflare support
    if "cf-ray" in request.headers:
        metadata["cf_ray"] = request.headers["cf-ray"]

    # CF-IPCountry: ISO 3166-1 Alpha 2 country code
    # Useful for geo-blocking and attack pattern analysis
    if "cf-ipcountry" in request.headers:
        metadata["cf_country"] = request.headers["cf-ipcountry"]

    # CF-Visitor: Original protocol (http/https) before Cloudflare
    # Useful for HSTS policy enforcement and security auditing
    if "cf-visitor" in request.headers:
        metadata["cf_visitor"] = request.headers["cf-visitor"]

    # CF-Request-ID: Request ID (available on Enterprise plans)
    if "cf-request-id" in request.headers:
        metadata["cf_request_id"] = request.headers["cf-request-id"]

    return metadata


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

            # Use the user_id from the block_info if available, otherwise None
            # Note: Some rate limit hits occur before authentication, so user may not be known
            # The user_id column in security_events is nullable to handle anonymous attempts
            user_id = block_info.user_id if block_info.user_id else None

            # Extract Cloudflare metadata for enhanced logging
            cf_metadata = get_cloudflare_metadata(request)

            # Build details dict with all available information
            log_details = {
                "endpoint": endpoint,
                "remaining_seconds": block_info.remaining_seconds,
                "failed_attempts": block_info.failed_attempts,
                "reason": block_info.reason,
                "lockout_type": block_info.lockout_type,
            }

            # Add Cloudflare metadata if available
            if cf_metadata:
                log_details["cloudflare"] = cf_metadata

            try:
                await SecurityEventService.log_rate_limit_hit(
                    session=session,
                    user_id=user_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    details=log_details,
                )
            except Exception:
                # Don't let logging failures prevent rate limiting from working
                logger.exception(
                    f"Failed to log rate limit hit for IP {ip_address} "
                    f"accessing {endpoint}"
                )

            # Structured logging for monitoring and alerting
            cf_ray_info = f", CF-Ray: {cf_metadata.get('cf_ray')}" if cf_metadata.get('cf_ray') else ""
            cf_country_info = f", Country: {cf_metadata.get('cf_country')}" if cf_metadata.get('cf_country') else ""

            logger.warning(
                f"Rate limit hit: IP {ip_address} blocked from accessing {endpoint}. "
                f"Attempts: {block_info.failed_attempts}, "
                f"Remaining: {block_info.remaining_seconds}s, "
                f"Reason: {block_info.reason}"
                f"{cf_ray_info}{cf_country_info}"
            )

            raise HTTPException(
                status_code=429,
                detail="Too many failed attempts. Please try again later.",
                headers={"Retry-After": str(remaining_minutes * 60)},
            )

    return ip_address


def secure_rate_limit_key(request: Request) -> str:
    """
    Secure key function for slowapi rate limiting.

    This function uses get_client_ip to extract the real client IP address,
    which validates proxy headers against trusted proxies to prevent IP spoofing.

    Args:
        request: The FastAPI request object

    Returns:
        Client IP address if available, "unknown" otherwise

    Usage:
        ```python
        from slowapi import Limiter
        from app.dependencies.rate_limit import secure_rate_limit_key

        limiter = Limiter(key_func=secure_rate_limit_key)
        ```

    Security Note:
        This function prevents IP spoofing attacks by only trusting proxy headers
        from configured trusted proxies (TRUSTED_PROXIES env var) or Cloudflare IPs.
        See get_client_ip() documentation for proxy configuration requirements.
    """
    client_ip = get_client_ip(request)
    return client_ip or "unknown"
