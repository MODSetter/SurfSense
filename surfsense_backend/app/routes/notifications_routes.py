"""
Notifications API routes.
These endpoints allow marking notifications as read and fetching older notifications.
Electric SQL automatically syncs the changes to all connected clients for recent items.
For older items (beyond the sync window), use the list endpoint.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Notification, User, get_async_session
from app.users import current_active_user

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationResponse(BaseModel):
    """Response model for a single notification."""

    id: int
    user_id: str
    search_space_id: Optional[int]
    type: str
    title: str
    message: str
    read: bool
    metadata: dict
    created_at: str
    updated_at: Optional[str]

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    """Response for listing notifications with pagination."""

    items: list[NotificationResponse]
    total: int
    has_more: bool
    next_offset: Optional[int]


class MarkReadResponse(BaseModel):
    """Response for mark as read operations."""

    success: bool
    message: str


class MarkAllReadResponse(BaseModel):
    """Response for mark all as read operation."""

    success: bool
    message: str
    updated_count: int


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    search_space_id: Optional[int] = Query(None, description="Filter by search space ID"),
    type_filter: Optional[str] = Query(None, alias="type", description="Filter by notification type"),
    before_date: Optional[str] = Query(None, description="Get notifications before this ISO date (for pagination)"),
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
    count_query = select(func.count(Notification.id)).where(Notification.user_id == user.id)
    
    # Filter by search space (include null search_space_id for global notifications)
    if search_space_id is not None:
        query = query.where(
            (Notification.search_space_id == search_space_id) | 
            (Notification.search_space_id.is_(None))
        )
        count_query = count_query.where(
            (Notification.search_space_id == search_space_id) | 
            (Notification.search_space_id.is_(None))
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
    query = query.order_by(desc(Notification.created_at)).offset(offset).limit(limit + 1)
    
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
        items.append(NotificationResponse(
            id=notification.id,
            user_id=str(notification.user_id),
            search_space_id=notification.search_space_id,
            type=notification.type,
            title=notification.title,
            message=notification.message,
            read=notification.read,
            metadata=notification.notification_metadata or {},
            created_at=notification.created_at.isoformat() if notification.created_at else "",
            updated_at=notification.updated_at.isoformat() if notification.updated_at else None,
        ))
    
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
