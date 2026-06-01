"""Response schemas for run sub-resources."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.automations.persistence.enums.run_status import RunStatus


class RunSummary(BaseModel):
    """Lightweight run view for list endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    automation_id: int
    trigger_id: int | None = None
    status: RunStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime


class RunDetail(RunSummary):
    """Full run view including snapshot, results and artifacts."""

    definition_snapshot: dict[str, Any]
    inputs: dict[str, Any]
    step_results: list[dict[str, Any]]
    output: dict[str, Any] | None = None
    artifacts: list[dict[str, Any]]
    error: dict[str, Any] | None = None


class RunList(BaseModel):
    """Paginated list of runs."""

    items: list[RunSummary]
    total: int
