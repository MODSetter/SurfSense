"""Admin routes — superuser-only operations."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import (
    SubscriptionRequest,
    SubscriptionRequestStatus,
    SubscriptionStatus,
    User,
    get_async_session,
)
from app.users import current_superuser

router = APIRouter(prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class SubscriptionRequestItem(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    user_email: str
    plan_id: str
    status: str
    created_at: datetime
    approved_at: datetime | None = None
    approved_by: uuid.UUID | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# List pending subscription requests
# ---------------------------------------------------------------------------


@router.get(
    "/subscription-requests",
    response_model=list[SubscriptionRequestItem],
)
async def list_subscription_requests(
    admin: User = Depends(current_superuser),
    db_session: AsyncSession = Depends(get_async_session),
) -> list[SubscriptionRequestItem]:
    """Return all pending subscription requests."""
    result = await db_session.execute(
        select(SubscriptionRequest)
        .where(SubscriptionRequest.status == SubscriptionRequestStatus.PENDING)
        .order_by(SubscriptionRequest.created_at.asc())
    )
    requests = result.scalars().all()

    # Collect user IDs and batch-load to avoid N+1
    user_ids = [req.user_id for req in requests]
    email_map: dict[uuid.UUID, str] = {}
    if user_ids:
        user_rows = await db_session.execute(select(User).where(User.id.in_(user_ids)))
        for u in user_rows.scalars():
            email_map[u.id] = u.email

    items: list[SubscriptionRequestItem] = [
        SubscriptionRequestItem(
            id=req.id,
            user_id=req.user_id,
            user_email=email_map.get(req.user_id, "<deleted>"),
            plan_id=req.plan_id,
            status=req.status.value,
            created_at=req.created_at,
            approved_at=req.approved_at,
            approved_by=req.approved_by,
        )
        for req in requests
    ]
    return items


# ---------------------------------------------------------------------------
# Approve a subscription request
# ---------------------------------------------------------------------------


@router.post(
    "/subscription-requests/{request_id}/approve",
    response_model=SubscriptionRequestItem,
)
async def approve_subscription_request(
    request_id: uuid.UUID,
    admin: User = Depends(current_superuser),
    db_session: AsyncSession = Depends(get_async_session),
) -> SubscriptionRequestItem:
    """Approve a pending subscription request and activate the user's subscription."""
    result = await db_session.execute(
        select(SubscriptionRequest)
        .where(SubscriptionRequest.id == request_id)
        .with_for_update()
    )
    req = result.scalar_one_or_none()
    if req is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription request not found.",
        )
    if req.status != SubscriptionRequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Request is already {req.status.value}.",
        )

    user_result = await db_session.execute(
        select(User).where(User.id == req.user_id).with_for_update()
    )
    req_user = user_result.scalar_one_or_none()
    if req_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )

    # Activate subscription
    plan_limits = config.PLAN_LIMITS.get(req.plan_id, config.PLAN_LIMITS["free"])
    req_user.subscription_status = SubscriptionStatus.ACTIVE
    req_user.plan_id = req.plan_id
    req_user.monthly_token_limit = plan_limits["monthly_token_limit"]
    req_user.pages_limit = max(req_user.pages_used or 0, plan_limits["pages_limit"])
    req_user.tokens_used_this_month = 0
    req_user.token_reset_date = datetime.now(UTC).date()

    # Mark request approved
    now = datetime.now(UTC)
    req.status = SubscriptionRequestStatus.APPROVED
    req.approved_at = now
    req.approved_by = admin.id

    await db_session.commit()
    await db_session.refresh(req)

    user_result2 = await db_session.execute(select(User).where(User.id == req.user_id))
    req_user2 = user_result2.scalar_one_or_none()
    email = req_user2.email if req_user2 else "<deleted>"

    return SubscriptionRequestItem(
        id=req.id,
        user_id=req.user_id,
        user_email=email,
        plan_id=req.plan_id,
        status=req.status.value,
        created_at=req.created_at,
        approved_at=req.approved_at,
        approved_by=req.approved_by,
    )


# ---------------------------------------------------------------------------
# Reject a subscription request
# ---------------------------------------------------------------------------


@router.post(
    "/subscription-requests/{request_id}/reject",
    response_model=SubscriptionRequestItem,
)
async def reject_subscription_request(
    request_id: uuid.UUID,
    admin: User = Depends(current_superuser),
    db_session: AsyncSession = Depends(get_async_session),
) -> SubscriptionRequestItem:
    """Reject a pending subscription request."""
    result = await db_session.execute(
        select(SubscriptionRequest).where(SubscriptionRequest.id == request_id)
    )
    req = result.scalar_one_or_none()
    if req is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription request not found.",
        )
    if req.status != SubscriptionRequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Request is already {req.status.value}.",
        )

    req.status = SubscriptionRequestStatus.REJECTED

    await db_session.commit()
    await db_session.refresh(req)

    user_result = await db_session.execute(select(User).where(User.id == req.user_id))
    req_user = user_result.scalar_one_or_none()
    email = req_user.email if req_user else "<deleted>"

    return SubscriptionRequestItem(
        id=req.id,
        user_id=req.user_id,
        user_email=email,
        plan_id=req.plan_id,
        status=req.status.value,
        created_at=req.created_at,
        approved_at=req.approved_at,
        approved_by=req.approved_by,
    )
