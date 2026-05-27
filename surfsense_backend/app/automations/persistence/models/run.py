"""``automation_runs`` table — immutable per-fire execution record."""

from __future__ import annotations

from sqlalchemy import (
    TIMESTAMP,
    Column,
    Enum as SQLAlchemyEnum,
    ForeignKey,
    Integer,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.db import BaseModel, TimestampMixin

from ..enums.run_status import RunStatus


class AutomationRun(BaseModel, TimestampMixin):
    __tablename__ = "automation_runs"

    automation_id = Column(
        Integer,
        ForeignKey("automations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    trigger_id = Column(
        Integer,
        ForeignKey("automation_triggers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    status = Column(
        SQLAlchemyEnum(RunStatus, name="automation_run_status"),
        nullable=False,
        default=RunStatus.PENDING,
        server_default=RunStatus.PENDING.value,
        index=True,
    )

    # locked at fire time so historical runs always show the exact code path
    definition_snapshot = Column(JSONB, nullable=False)

    # merged & validated inputs the run was dispatched with
    # (trigger.static_inputs ∪ producer runtime data, static wins on collision)
    inputs = Column(JSONB, nullable=False, server_default="{}")
    # one entry per executed step; agent_task entries carry their own
    # `agent_session_id` inside their entry
    step_results = Column(JSONB, nullable=False, server_default="[]")
    output = Column(JSONB, nullable=True)
    artifacts = Column(JSONB, nullable=False, server_default="[]")
    error = Column(JSONB, nullable=True)

    started_at = Column(TIMESTAMP(timezone=True), nullable=True)
    finished_at = Column(TIMESTAMP(timezone=True), nullable=True)

    automation = relationship("Automation", back_populates="runs")
    trigger = relationship("AutomationTrigger", back_populates="runs")
