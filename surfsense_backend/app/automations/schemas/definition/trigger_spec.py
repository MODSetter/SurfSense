"""``TriggerSpec`` — one entry in the definition's ``triggers[]`` array."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TriggerSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = Field(..., min_length=1, description="Trigger type; resolved via registry.")
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Type-specific params; validated against the trigger's schema.",
    )
