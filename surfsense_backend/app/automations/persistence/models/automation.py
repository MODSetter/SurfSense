"""``automations`` table — editable, versioned automation definition."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    TIMESTAMP,
    Column,
    Enum as SQLAlchemyEnum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db import BaseModel, TimestampMixin

from ..enums.automation_status import AutomationStatus


class Automation(BaseModel, TimestampMixin):
    __tablename__ = "automations"

    search_space_id = Column(
        Integer,
        ForeignKey("searchspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    created_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    status = Column(
        SQLAlchemyEnum(AutomationStatus, name="automation_status"),
        nullable=False,
        default=AutomationStatus.ACTIVE,
        server_default=AutomationStatus.ACTIVE.value,
        index=True,
    )

    definition = Column(JSONB, nullable=False)

    version = Column(Integer, nullable=False, default=1, server_default="1")

    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        index=True,
    )

    search_space = relationship("SearchSpace", back_populates="automations")
    created_by = relationship("User", back_populates="automations")
    triggers = relationship(
        "AutomationTrigger",
        back_populates="automation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    runs = relationship(
        "AutomationRun",
        back_populates="automation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
