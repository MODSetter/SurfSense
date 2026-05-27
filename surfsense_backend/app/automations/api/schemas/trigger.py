"""Request/response schemas for trigger sub-resources."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.automations.persistence.enums.trigger_type import TriggerType


class TriggerCreate(BaseModel):
    """Attach a trigger to an automation."""

    model_config = ConfigDict(extra="forbid")

    type: TriggerType
    params: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class TriggerUpdate(BaseModel):
    """Partial update of an existing trigger."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    params: dict[str, Any] | None = None


class TriggerDetail(BaseModel):
    """Trigger as returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    type: TriggerType
    params: dict[str, Any]
    enabled: bool
    last_fired_at: datetime | None = None
    next_fire_at: datetime | None = None
    created_at: datetime
