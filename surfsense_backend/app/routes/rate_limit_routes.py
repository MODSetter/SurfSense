"""
Rate Limiting Management API routes.

Provides endpoints for viewing and managing IP blocks and rate limiting.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import User, get_async_session
from app.routes.two_fa_routes import get_request_metadata
from app.services.rate_limit_service import (
    BlockedIP,
    RateLimitStats,
    rate_limit_service,
)
from app.services.security_event_service import security_event_service
from app.users import current_active_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/rate-limiting", tags=["rate-limiting"])


class BlockedIPResponse(BaseModel):
    """Response model for a single blocked IP."""

    ip_address: str
    user_id: str | None
    username: str | None
    blocked_at: str
    expires_at: str
    remaining_seconds: int
    failed_attempts: int
    reason: str
    lockout_type: str


class BlockedIPsListResponse(BaseModel):
    """Response model for list of blocked IPs."""

    blocked_ips: list[BlockedIPResponse]
    total_count: int
    statistics: dict[str, Any]


class UnlockIPRequest(BaseModel):
    """Request to unlock an IP address."""

    reason: str | None = None


class BulkUnlockRequest(BaseModel):
    """Request to unlock multiple IP addresses."""

    ip_addresses: list[str]
    reason: str | None = None


class UnlockResponse(BaseModel):
    """Response for unlock operation."""

    success: bool
    message: str
    ip_address: str | None = None


class BulkUnlockResponse(BaseModel):
    """Response for bulk unlock operation."""

    success: bool
    unlocked_count: int
    failed: list[str]
    message: str


def require_admin(user: User = Depends(current_active_user)) -> User:
    """Dependency to ensure user is an admin/superuser."""
    if not user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="Admin privileges required for this operation",
        )
    return user


@router.get("/blocked-ips", response_model=BlockedIPsListResponse)
async def get_blocked_ips(
    user: User = Depends(current_active_user),
):
    """
    Get list of currently blocked IP addresses.

    Returns all blocked IPs with their details and statistics.
    Regular users see all blocks, but only admins can unlock them.
    """
    try:
        # Get all blocked IPs
        blocked_ips = rate_limit_service.get_all_blocked_ips()

        # Get statistics
        stats = rate_limit_service.get_statistics()

        # Convert to response format
        blocked_ip_responses = [
            BlockedIPResponse(
                ip_address=block.ip_address,
                user_id=block.user_id,
                username=block.username,
                blocked_at=block.blocked_at.isoformat(),
                expires_at=block.expires_at.isoformat(),
                remaining_seconds=block.remaining_seconds,
                failed_attempts=block.failed_attempts,
                reason=block.reason,
                lockout_type=block.lockout_type,
            )
            for block in blocked_ips
        ]

        return BlockedIPsListResponse(
            blocked_ips=blocked_ip_responses,
            total_count=len(blocked_ip_responses),
            statistics={
                "active_blocks": stats.active_blocks,
                "blocks_24h": stats.blocks_24h,
                "blocks_7d": stats.blocks_7d,
                "avg_lockout_duration": stats.avg_lockout_duration,
            },
        )

    except Exception as e:
        logger.error(f"Failed to get blocked IPs: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve blocked IPs",
        )


@router.post("/unlock/{ip_address}", response_model=UnlockResponse)
async def unlock_ip(
    ip_address: str,
    unlock_request: UnlockIPRequest,
    http_request: Request,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Manually unlock a blocked IP address.

    Requires admin privileges. Clears all rate limiting data for the IP
    and logs the unlock action.
    """
    try:
        # Get request metadata
        admin_ip, user_agent = get_request_metadata(http_request)

        # Check if IP is actually blocked
        is_blocked, block = rate_limit_service.is_ip_blocked(ip_address)
        if not is_blocked:
            return UnlockResponse(
                success=False,
                message=f"IP address {ip_address} is not currently blocked",
                ip_address=ip_address,
            )

        # Unlock the IP
        success = rate_limit_service.unlock_ip(
            ip_address=ip_address,
            admin_user_id=str(admin.id),
            reason=unlock_request.reason,
        )

        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to unlock IP address",
            )

        # Log the unlock event
        await security_event_service.log_rate_limit_admin_unlock(
            session=session,
            user_id=admin.id,
            ip_address=admin_ip,
            user_agent=user_agent,
            details={
                "unlocked_ip": ip_address,
                "reason": unlock_request.reason or "Not specified",
                "original_block_reason": block.reason if block else "Unknown",
            },
        )

        logger.info(
            f"Admin {admin.email} unlocked IP {ip_address} "
            f"(reason: {unlock_request.reason or 'Not specified'})"
        )

        return UnlockResponse(
            success=True,
            message=f"IP address {ip_address} has been unlocked",
            ip_address=ip_address,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to unlock IP {ip_address}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to unlock IP address",
        )


@router.post("/bulk-unlock", response_model=BulkUnlockResponse)
async def bulk_unlock_ips(
    bulk_request: BulkUnlockRequest,
    http_request: Request,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Unlock multiple IP addresses at once.

    Requires admin privileges. Unlocks all specified IPs and returns
    count of successful unlocks and list of any failures.
    """
    try:
        if not bulk_request.ip_addresses:
            raise HTTPException(
                status_code=400,
                detail="No IP addresses provided",
            )

        # Get request metadata
        admin_ip, user_agent = get_request_metadata(http_request)

        # Unlock all IPs
        unlocked_count, failed = rate_limit_service.bulk_unlock_ips(
            ip_addresses=bulk_request.ip_addresses,
            admin_user_id=str(admin.id),
            reason=bulk_request.reason,
        )

        # Log the bulk unlock event
        await security_event_service.log_rate_limit_admin_unlock(
            session=session,
            user_id=admin.id,
            ip_address=admin_ip,
            user_agent=user_agent,
            details={
                "unlocked_ips": bulk_request.ip_addresses,
                "unlocked_count": unlocked_count,
                "failed_count": len(failed),
                "reason": bulk_request.reason or "Not specified",
            },
        )

        logger.info(
            f"Admin {admin.email} bulk unlocked {unlocked_count} IPs "
            f"({len(failed)} failed)"
        )

        return BulkUnlockResponse(
            success=len(failed) == 0,
            unlocked_count=unlocked_count,
            failed=failed,
            message=f"Unlocked {unlocked_count} IP(s). {len(failed)} failed.",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to bulk unlock IPs: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to unlock IP addresses",
        )


@router.get("/stats")
async def get_rate_limit_stats(
    user: User = Depends(current_active_user),
):
    """
    Get rate limiting statistics.

    Returns statistics about active blocks and recent activity.
    """
    try:
        stats = rate_limit_service.get_statistics()

        return {
            "active_blocks": stats.active_blocks,
            "blocks_24h": stats.blocks_24h,
            "blocks_7d": stats.blocks_7d,
            "avg_lockout_duration": stats.avg_lockout_duration,
        }

    except Exception as e:
        logger.error(f"Failed to get rate limit statistics: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve statistics",
        )
