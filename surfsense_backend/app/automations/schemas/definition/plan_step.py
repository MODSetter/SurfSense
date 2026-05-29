"""``PlanStep`` — one step in the sequential plan."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(..., min_length=1, description="Unique within the plan.")
    action: str = Field(
        ..., min_length=1, description="Action type; resolved via registry."
    )
    when: str | None = Field(
        default=None,
        description="Optional predicate; step is skipped when falsy.",
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Action-type-specific params; rendered at execute time.",
    )
    output_as: str | None = Field(
        default=None,
        description="Bind step output under this name. Defaults to step_id.",
    )
    max_retries: int | None = Field(default=None, ge=0)
    timeout_seconds: int | None = Field(default=None, gt=0)
