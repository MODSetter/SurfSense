"""Per-user inbox notifications, synced to clients via Zero."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db import BaseModel, TimestampMixin


class Notification(BaseModel, TimestampMixin):
    __tablename__ = "notifications"
    __table_args__ = (
        # Serves unread-count queries.
        Index(
            "ix_notifications_user_read_type_created",
            "user_id",
            "read",
            "type",
            "created_at",
        ),
        # Serves the paginated inbox list query.
        Index(
            "ix_notifications_user_space_created",
            "user_id",
            "search_space_id",
            "created_at",
        ),
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    search_space_id = Column(
        Integer,
        ForeignKey("searchspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    type = Column(String(50), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    read = Column(
        Boolean, nullable=False, default=False, server_default=text("false"), index=True
    )
    notification_metadata = Column("metadata", JSONB, nullable=True, default={})
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=True,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        index=True,
    )

    user = relationship("User", back_populates="notifications")
    search_space = relationship("SearchSpace", back_populates="notifications")
