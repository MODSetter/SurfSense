"""Request/response schemas for the ``Automation`` resource."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.automations.persistence.enums.automation_status import AutomationStatus
from app.automations.schemas.definition import AutomationDefinition

from .trigger import TriggerCreate, TriggerDetail


class AutomationCreate(BaseModel):
    """Create an automation, optionally with initial triggers (atomic)."""

    model_config = ConfigDict(extra="forbid")

    workspace_id: int
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    definition: AutomationDefinition
    triggers: list[TriggerCreate] = Field(default_factory=list)


class AutomationUpdate(BaseModel):
    """Partial update of an automation. Triggers are managed separately."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    status: AutomationStatus | None = None
    definition: AutomationDefinition | None = None


class AutomationSummary(BaseModel):
    """Lightweight automation view for list endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    name: str
    description: str | None = None
    status: AutomationStatus
    version: int
    created_at: datetime
    updated_at: datetime


class AutomationDetail(AutomationSummary):
    """Full automation view including definition and attached triggers."""

    definition: AutomationDefinition
    triggers: list[TriggerDetail] = Field(default_factory=list)


class AutomationList(BaseModel):
    """Paginated list of automations."""

    items: list[AutomationSummary]
    total: int
