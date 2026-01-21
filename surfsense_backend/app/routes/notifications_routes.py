"""
Notifications API routes.
These endpoints allow marking notifications as read.
Electric SQL automatically syncs the changes to all connected clients.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Notification, User, get_async_session
from app.users import current_active_user

router = APIRouter(prefix="/notifications", tags=["notifications"])


class MarkReadResponse(BaseModel):
    """Response for mark as read operations."""

    success: bool
    message: str


class MarkAllReadResponse(BaseModel):
    """Response for mark all as read operation."""

    success: bool
    message: str
    updated_count: int


class ArchiveRequest(BaseModel):
    """Request body for archive/unarchive operations."""

    archived: bool


class ArchiveResponse(BaseModel):
    """Response for archive operations."""

    success: bool
    message: str


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


@router.patch("/{notification_id}/archive", response_model=ArchiveResponse)
async def archive_notification(
    notification_id: int,
    request: ArchiveRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> ArchiveResponse:
    """
    Archive or unarchive a notification.

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

    # Update the notification
    notification.archived = request.archived
    await session.commit()

    action = "archived" if request.archived else "unarchived"
    return ArchiveResponse(
        success=True,
        message=f"Notification {action}",
    )
