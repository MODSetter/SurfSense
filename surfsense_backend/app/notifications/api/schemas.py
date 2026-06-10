"""Response shapes for the notifications API."""

from __future__ import annotations

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    """A single notification."""

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
    """A page of notifications."""

    items: list[NotificationResponse]
    total: int
    has_more: bool
    next_offset: int | None


class MarkReadResponse(BaseModel):
    """Outcome of marking one notification read."""

    success: bool
    message: str


class MarkAllReadResponse(BaseModel):
    """Outcome of marking every notification read."""

    success: bool
    message: str
    updated_count: int


class SourceTypeItem(BaseModel):
    """A source type with its category and count."""

    key: str
    type: str
    category: str  # "connector" or "document"
    count: int


class SourceTypesResponse(BaseModel):
    """Source types available for the Status tab filter."""

    sources: list[SourceTypeItem]


class UnreadCountResponse(BaseModel):
    """Unread totals, split by sync-window recency."""

    total_unread: int
    recent_unread: int


class CategoryUnreadCount(BaseModel):
    total_unread: int
    recent_unread: int


class BatchUnreadCountResponse(BaseModel):
    """Per-category unread counts in one response."""

    comments: CategoryUnreadCount
    status: CategoryUnreadCount
