"""``automation_triggers`` table — one row per (automation, trigger-instance) pair."""

from __future__ import annotations

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    Column,
    Enum as SQLAlchemyEnum,
    ForeignKey,
    Integer,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.db import BaseModel, TimestampMixin

from ..enums.trigger_type import TriggerType


class AutomationTrigger(BaseModel, TimestampMixin):
    __tablename__ = "automation_triggers"

    automation_id = Column(
        Integer,
        ForeignKey("automations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    type = Column(
        SQLAlchemyEnum(TriggerType, name="automation_trigger_type"),
        nullable=False,
        index=True,
    )

    config = Column(JSONB, nullable=False)

    enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
    )

    last_fired_at = Column(TIMESTAMP(timezone=True), nullable=True)
