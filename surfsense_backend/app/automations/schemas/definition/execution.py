"""``Execution`` — automation-wide execution defaults (overridable per step)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .plan_step import PlanStep


class Execution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timeout_seconds: int = Field(
        default=600, gt=0, description="Wall-clock cap for the run."
    )
    max_retries: int = Field(default=2, ge=0, description="Per-step retry budget.")
    retry_backoff: Literal["exponential", "linear", "none"] = "exponential"
    concurrency: Literal["drop_if_running", "queue", "always"] = "drop_if_running"
    on_failure: list[PlanStep] = Field(
        default_factory=list,
        description="Steps run when the main plan fails after retries.",
    )
