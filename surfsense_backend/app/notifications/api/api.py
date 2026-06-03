"""HTTP routes for the notifications inbox (list, counts, mark-read)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, desc, func, literal, literal_column, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import User, get_async_session
from app.notifications.api.schemas import (
    BatchUnreadCountResponse,
    CategoryUnreadCount,
    MarkAllReadResponse,
    MarkReadResponse,
    NotificationListResponse,
    NotificationResponse,
    SourceTypeItem,
    SourceTypesResponse,
    UnreadCountResponse,
)
from app.notifications.constants import CATEGORY_TYPES, SYNC_WINDOW_DAYS
from app.notifications.persistence import Notification
from app.notifications.types import NotificationCategory, NotificationType
from app.users import current_active_user

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/unread-counts-batch", response_model=BatchUnreadCountResponse)
async def get_unread_counts_batch(
    search_space_id: int | None = Query(None, description="Filter by search space ID"),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> BatchUnreadCountResponse:
    """Unread counts for every category in a single query."""
    cutoff_date = datetime.now(UTC) - timedelta(days=SYNC_WINDOW_DAYS)

    base_filter = [
        Notification.user_id == user.id,
        Notification.read == False,  # noqa: E712
    ]

    if search_space_id is not None:
        # Include global (null search-space) notifications.
        base_filter.append(
            (Notification.search_space_id == search_space_id)
            | (Notification.search_space_id.is_(None))
        )

    is_comments = Notification.type.in_(CATEGORY_TYPES["comments"])
    is_status = Notification.type.in_(CATEGORY_TYPES["status"])
    is_recent = Notification.created_at > cutoff_date

    query = select(
        func.count(case((is_comments, Notification.id))).label("comments_total"),
        func.count(case((is_comments & is_recent, Notification.id))).label(
            "comments_recent"
        ),
        func.count(case((is_status, Notification.id))).label("status_total"),
        func.count(case((is_status & is_recent, Notification.id))).label(
            "status_recent"
        ),
    ).where(*base_filter)

    result = await session.execute(query)
    row = result.one()

    return BatchUnreadCountResponse(
        comments=CategoryUnreadCount(
            total_unread=row.comments_total,
            recent_unread=row.comments_recent,
        ),
        status=CategoryUnreadCount(
            total_unread=row.status_total,
            recent_unread=row.status_recent,
        ),
    )


@router.get("/source-types", response_model=SourceTypesResponse)
async def get_notification_source_types(
    search_space_id: int | None = Query(None, description="Filter by search space ID"),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> SourceTypesResponse:
    """Distinct connector/document source types for the Status tab filter."""
    base_filter = [Notification.user_id == user.id]

    if search_space_id is not None:
        # Include global (null search-space) notifications.
        base_filter.append(
            (Notification.search_space_id == search_space_id)
            | (Notification.search_space_id.is_(None))
        )

    connector_type_expr = Notification.notification_metadata["connector_type"].astext
    connector_query = (
        select(
            connector_type_expr.label("source_type"),
            literal("connector").label("category"),
            func.count(Notification.id).label("cnt"),
        )
        .where(
            *base_filter,
            Notification.type.in_(("connector_indexing", "connector_deletion")),
            connector_type_expr.isnot(None),
        )
        .group_by(literal_column("source_type"))
    )

    document_type_expr = Notification.notification_metadata["document_type"].astext
    document_query = (
        select(
            document_type_expr.label("source_type"),
            literal("document").label("category"),
            func.count(Notification.id).label("cnt"),
        )
        .where(
            *base_filter,
            Notification.type.in_(("document_processing",)),
            document_type_expr.isnot(None),
        )
        .group_by(literal_column("source_type"))
    )

    connector_result = await session.execute(connector_query)
    document_result = await session.execute(document_query)

    sources = []
    for source_type, category, count in [
        *connector_result.all(),
        *document_result.all(),
    ]:
        if not source_type:
            continue
        sources.append(
            SourceTypeItem(
                key=f"{category}:{source_type}",
                type=source_type,
                category=category,
                count=count,
            )
        )

    return SourceTypesResponse(sources=sources)


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    search_space_id: int | None = Query(None, description="Filter by search space ID"),
    type_filter: NotificationType | None = Query(
        None, alias="type", description="Filter by notification type"
    ),
    category: NotificationCategory | None = Query(
        None, description="Filter by category: 'comments' or 'status'"
    ),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> UnreadCountResponse:
    """Total and recent (within sync window) unread counts for the user.

    Returning both lets a client hold the older count static while
    live-syncing the recent ones.
    """
    cutoff_date = datetime.now(UTC) - timedelta(days=SYNC_WINDOW_DAYS)

    base_filter = [
        Notification.user_id == user.id,
        Notification.read == False,  # noqa: E712
    ]

    if search_space_id is not None:
        # Include global (null search-space) notifications.
        base_filter.append(
            (Notification.search_space_id == search_space_id)
            | (Notification.search_space_id.is_(None))
        )

    if type_filter:
        base_filter.append(Notification.type == type_filter)

    if category:
        base_filter.append(Notification.type.in_(CATEGORY_TYPES[category]))

    total_query = select(func.count(Notification.id)).where(*base_filter)
    total_result = await session.execute(total_query)
    total_unread = total_result.scalar() or 0

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
    category: NotificationCategory | None = Query(
        None, description="Filter by category: 'comments' or 'status'"
    ),
    source_type: str | None = Query(
        None,
        description="Filter by source type, e.g. 'connector:GITHUB_CONNECTOR' or 'doctype:FILE'",
    ),
    filter: str | None = Query(
        None,
        description="Filter preset: 'unread' for unread only, 'errors' for failed/error items only",
    ),
    before_date: str | None = Query(
        None, description="Get notifications before this ISO date (for pagination)"
    ),
    search: str | None = Query(
        None, description="Search notifications by title or message (case-insensitive)"
    ),
    limit: int = Query(50, ge=1, le=100, description="Number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> NotificationListResponse:
    """Paginated inbox fallback for items outside the Zero sync window."""
    query = select(Notification).where(Notification.user_id == user.id)
    count_query = select(func.count(Notification.id)).where(
        Notification.user_id == user.id
    )

    if search_space_id is not None:
        # Include global (null search-space) notifications.
        query = query.where(
            (Notification.search_space_id == search_space_id)
            | (Notification.search_space_id.is_(None))
        )
        count_query = count_query.where(
            (Notification.search_space_id == search_space_id)
            | (Notification.search_space_id.is_(None))
        )

    if type_filter:
        query = query.where(Notification.type == type_filter)
        count_query = count_query.where(Notification.type == type_filter)

    if category:
        cat_types = CATEGORY_TYPES[category]
        query = query.where(Notification.type.in_(cat_types))
        count_query = count_query.where(Notification.type.in_(cat_types))

    # source_type encodes the JSONB facet to match: 'connector:<type>' or 'doctype:<type>'.
    if source_type:
        if source_type.startswith("connector:"):
            connector_val = source_type[len("connector:") :]
            source_filter = Notification.type.in_(
                ("connector_indexing", "connector_deletion")
            ) & (
                Notification.notification_metadata["connector_type"].astext
                == connector_val
            )
            query = query.where(source_filter)
            count_query = count_query.where(source_filter)
        elif source_type.startswith("doctype:"):
            doctype_val = source_type[len("doctype:") :]
            source_filter = Notification.type.in_(("document_processing",)) & (
                Notification.notification_metadata["document_type"].astext
                == doctype_val
            )
            query = query.where(source_filter)
            count_query = count_query.where(source_filter)

    if filter == "unread":
        unread_filter = Notification.read == False  # noqa: E712
        query = query.where(unread_filter)
        count_query = count_query.where(unread_filter)
    elif filter == "errors":
        error_filter = (Notification.type == "page_limit_exceeded") | (
            Notification.notification_metadata["status"].astext == "failed"
        )
        query = query.where(error_filter)
        count_query = count_query.where(error_filter)

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

    if search:
        search_term = f"%{search}%"
        search_filter = Notification.title.ilike(
            search_term
        ) | Notification.message.ilike(search_term)
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Over-fetch by one to tell whether another page exists.
    query = (
        query.order_by(desc(Notification.created_at)).offset(offset).limit(limit + 1)
    )

    result = await session.execute(query)
    notifications = result.scalars().all()

    has_more = len(notifications) > limit
    if has_more:
        notifications = notifications[:limit]

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
    """Mark one of the user's notifications read; Zero syncs the change."""
    # Scope to the caller's own notifications.
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
    """Mark all of the user's notifications read; Zero syncs the changes."""
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
