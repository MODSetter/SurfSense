"""``automation_runs`` table — immutable per-fire execution record."""

from __future__ import annotations

from sqlalchemy import (
    TIMESTAMP,
    Column,
    Enum as SQLAlchemyEnum,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB

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

    trigger_payload = Column(JSONB, nullable=True)
    resolved_inputs = Column(JSONB, nullable=False, server_default="{}")
    step_results = Column(JSONB, nullable=False, server_default="[]")
    output = Column(JSONB, nullable=True)
    artifacts = Column(JSONB, nullable=False, server_default="[]")
    error = Column(JSONB, nullable=True)

    started_at = Column(TIMESTAMP(timezone=True), nullable=True)
    finished_at = Column(TIMESTAMP(timezone=True), nullable=True)

    agent_session_id = Column(String(200), nullable=True)
