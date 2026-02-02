"""
Notifications API routes.
These endpoints allow marking notifications as read and fetching older notifications.
Electric SQL automatically syncs the changes to all connected clients for recent items.
For older items (beyond the sync window), use the list endpoint.
"""

from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Notification, User, get_async_session
from app.users import current_active_user

router = APIRouter(prefix="/notifications", tags=["notifications"])

# Must match frontend SYNC_WINDOW_DAYS in use-inbox.ts
SYNC_WINDOW_DAYS = 14

# Valid notification types - must match frontend InboxItemTypeEnum
NotificationType = Literal[
    "connector_indexing", "document_processing", "new_mention", "page_limit_exceeded"
]


class NotificationResponse(BaseModel):
    """Response model for a single notification."""

    id: int
    user_id: str
    search_space_id: int | None
    type: str
    title: str
    message: str
    read: bool
    metadata: dict
    created_at: str
    updated_at: str | None

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    """Response for listing notifications with pagination."""

    items: list[NotificationResponse]
    total: int
    has_more: bool
    next_offset: int | None


class MarkReadResponse(BaseModel):
    """Response for mark as read operations."""

    success: bool
    message: str


class MarkAllReadResponse(BaseModel):
    """Response for mark all as read operation."""

    success: bool
    message: str
    updated_count: int


class UnreadCountResponse(BaseModel):
    """Response for unread count with split between recent and older items."""

    total_unread: int
    recent_unread: int  # Within SYNC_WINDOW_DAYS


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    search_space_id: int | None = Query(None, description="Filter by search space ID"),
    type_filter: NotificationType | None = Query(
        None, alias="type", description="Filter by notification type"
    ),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> UnreadCountResponse:
    """
    Get the total unread notification count for the current user.

    Returns both:
    - total_unread: All unread notifications (for accurate badge count)
    - recent_unread: Unread notifications within the sync window (last 14 days)

    This allows the frontend to calculate:
    - older_unread = total_unread - recent_unread (static until reconciliation)
    - Display count = older_unread + live_recent_count (from Electric SQL)
    """
    # Calculate cutoff date for sync window
    cutoff_date = datetime.now(UTC) - timedelta(days=SYNC_WINDOW_DAYS)

    # Base filter for user's unread notifications
    base_filter = [
        Notification.user_id == user.id,
        Notification.read == False,  # noqa: E712
    ]

    # Add search space filter if provided (include null for global notifications)
    if search_space_id is not None:
        base_filter.append(
            (Notification.search_space_id == search_space_id)
            | (Notification.search_space_id.is_(None))
        )

    # Filter by notification type if provided
    if type_filter:
        base_filter.append(Notification.type == type_filter)

    # Total unread count (all time)
    total_query = select(func.count(Notification.id)).where(*base_filter)
    total_result = await session.execute(total_query)
    total_unread = total_result.scalar() or 0

    # Recent unread count (within sync window)
    recent_query = select(func.count(Notification.id)).where(
        *base_filter,
        Notification.created_at > cutoff_date,
    )
    recent_result = await session.execute(recent_query)
    recent_unread = recent_result.scalar() or 0

    return UnreadCountResponse(
        total_unread=total_unread,
        recent_unread=recent_unread,
    )


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    search_space_id: int | None = Query(None, description="Filter by search space ID"),
    type_filter: NotificationType | None = Query(
        None, alias="type", description="Filter by notification type"
    ),
    before_date: str | None = Query(
        None, description="Get notifications before this ISO date (for pagination)"
    ),
    limit: int = Query(50, ge=1, le=100, description="Number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> NotificationListResponse:
    """
    List notifications for the current user with pagination.

    This endpoint is used as a fallback for older notifications that are
    outside the Electric SQL sync window (2 weeks).

    Use `before_date` to paginate through older notifications efficiently.
    """
    # Build base query
    query = select(Notification).where(Notification.user_id == user.id)
    count_query = select(func.count(Notification.id)).where(
        Notification.user_id == user.id
    )

    # Filter by search space (include null search_space_id for global notifications)
    if search_space_id is not None:
        query = query.where(
            (Notification.search_space_id == search_space_id)
            | (Notification.search_space_id.is_(None))
        )
        count_query = count_query.where(
            (Notification.search_space_id == search_space_id)
            | (Notification.search_space_id.is_(None))
        )

    # Filter by type
    if type_filter:
        query = query.where(Notification.type == type_filter)
        count_query = count_query.where(Notification.type == type_filter)

    # Filter by date (for efficient pagination of older items)
    if before_date:
        try:
            before_datetime = datetime.fromisoformat(before_date.replace("Z", "+00:00"))
            query = query.where(Notification.created_at < before_datetime)
            count_query = count_query.where(Notification.created_at < before_datetime)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format. Use ISO format (e.g., 2024-01-15T00:00:00Z)",
            ) from None

    # Get total count
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Apply ordering and pagination
    query = (
        query.order_by(desc(Notification.created_at)).offset(offset).limit(limit + 1)
    )

    # Execute query
    result = await session.execute(query)
    notifications = result.scalars().all()

    # Check if there are more items
    has_more = len(notifications) > limit
    if has_more:
        notifications = notifications[:limit]

    # Convert to response format
    items = []
    for notification in notifications:
        items.append(
            NotificationResponse(
                id=notification.id,
                user_id=str(notification.user_id),
                search_space_id=notification.search_space_id,
                type=notification.type,
                title=notification.title,
                message=notification.message,
                read=notification.read,
                metadata=notification.notification_metadata or {},
                created_at=notification.created_at.isoformat()
                if notification.created_at
                else "",
                updated_at=notification.updated_at.isoformat()
                if notification.updated_at
                else None,
            )
        )

    return NotificationListResponse(
        items=items,
        total=total,
        has_more=has_more,
        next_offset=offset + limit if has_more else None,
    )


@router.patch("/{notification_id}/read", response_model=MarkReadResponse)
async def mark_notification_as_read(
    notification_id: int,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> MarkReadResponse:
    """
    Mark a single notification as read.

    Electric SQL will automatically sync this change to all connected clients.
    """
    # Verify the notification belongs to the user
    result = await session.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user.id,
        )
    )
    notification = result.scalar_one_or_none()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    if notification.read:
        return MarkReadResponse(
            success=True,
            message="Notification already marked as read",
        )

    # Update the notification
    notification.read = True
    await session.commit()

    return MarkReadResponse(
        success=True,
        message="Notification marked as read",
    )


@router.patch("/read-all", response_model=MarkAllReadResponse)
async def mark_all_notifications_as_read(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> MarkAllReadResponse:
    """
    Mark all notifications as read for the current user.

    Electric SQL will automatically sync these changes to all connected clients.
    """
    # Update all unread notifications for the user
    result = await session.execute(
        update(Notification)
        .where(
            Notification.user_id == user.id,
            Notification.read == False,  # noqa: E712
        )
        .values(read=True)
    )
    await session.commit()

    updated_count = result.rowcount

    return MarkAllReadResponse(
        success=True,
        message=f"Marked {updated_count} notification(s) as read",
        updated_count=updated_count,
    )
