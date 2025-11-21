"""
Health check endpoints for monitoring and load balancing.

These endpoints bypass rate limiting and authentication to allow
external monitoring systems (like Cloudflare Health Checks, Kubernetes
liveness/readiness probes, or monitoring services) to check service health.

Security Note:
    These endpoints should be protected at the network level (firewall rules,
    Cloudflare Access, or IP allowlists) to prevent abuse. They intentionally
    bypass rate limiting to ensure monitoring works even during attacks.
"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    timestamp: str
    version: str = "1.0.0"
    checks: dict[str, str] | None = None


class DetailedHealthResponse(HealthResponse):
    """Detailed health check with individual component status."""

    database: str
    redis: str | None = None


@router.get("", response_model=HealthResponse)
@router.get("/", response_model=HealthResponse)
async def basic_health_check() -> HealthResponse:
    """
    Basic health check endpoint (no dependencies).

    Returns a simple OK response without checking any dependencies.
    Use this for basic uptime monitoring or as a Kubernetes liveness probe.

    Security:
    - No rate limiting
    - No authentication required
    - Should be protected by network-level controls

    Returns:
        HealthResponse with basic status
    """
    return HealthResponse(
        status="ok",
        timestamp=datetime.now(UTC).isoformat(),
    )


@router.get("/ready", response_model=DetailedHealthResponse)
async def readiness_check(
    session: AsyncSession = Depends(get_async_session),
) -> DetailedHealthResponse:
    """
    Readiness check endpoint with dependency verification.

    Checks that critical dependencies (database, Redis) are accessible.
    Use this for Kubernetes readiness probes or monitoring detailed health.

    This endpoint verifies:
    - Database connectivity
    - Redis connectivity (if configured)

    Security:
    - No rate limiting
    - No authentication required
    - Should be protected by network-level controls

    Returns:
        DetailedHealthResponse with component status

    Raises:
        HTTPException: 503 if any critical dependency is unhealthy
    """
    checks = {}
    all_healthy = True

    # Check database
    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
        db_status = "ok"
    except Exception as e:
        logger.exception("Database health check failed")
        checks["database"] = f"error: {str(e)[:100]}"
        db_status = "error"
        all_healthy = False

    # Check Redis (rate limiting dependency)
    redis_status = None
    try:
        from app.services.rate_limit_service import get_redis_client

        redis_client = get_redis_client()
        redis_client.ping()
        checks["redis"] = "ok"
        redis_status = "ok"
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")
        checks["redis"] = f"error: {str(e)[:100]}"
        redis_status = "error"
        # Redis is not critical for basic functionality
        # Don't mark as unhealthy if only Redis is down

    if not all_healthy:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "timestamp": datetime.now(UTC).isoformat(),
                "checks": checks,
            },
        )

    return DetailedHealthResponse(
        status="ok",
        timestamp=datetime.now(UTC).isoformat(),
        checks=checks,
        database=db_status,
        redis=redis_status,
    )


@router.get("/live", response_model=HealthResponse)
async def liveness_check() -> HealthResponse:
    """
    Liveness check endpoint (minimal dependencies).

    Simple check that the application is running and responding.
    Use this for Kubernetes liveness probes.

    Security:
    - No rate limiting
    - No authentication required
    - Should be protected by network-level controls

    Returns:
        HealthResponse with basic status
    """
    return HealthResponse(
        status="ok",
        timestamp=datetime.now(UTC).isoformat(),
    )
