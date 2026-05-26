"""``ExecutionBlock`` — the ``execution`` section of the automation definition."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .plan_step import PlanStep


class ExecutionBlock(BaseModel):
    """The ``execution`` block of an ``AutomationDefinition``.

    Carries automation-wide defaults that individual ``PlanStep``s
    can override. Every field has a sane default so an automation
    definition may omit the block entirely; in that case all defaults
    apply.

    ``on_failure`` is a secondary plan that runs only when the main
    ``plan`` fails after retries exhaust. It uses the same
    ``PlanStep`` shape as the main plan and shares the same execution
    semantics.
    """

    model_config = ConfigDict(extra="forbid")

    timeout_seconds: int = Field(
        default=600,
        gt=0,
        description=(
            "Hard wall-clock cap for the entire run. The executor "
            "transitions the run to ``timed_out`` when this is "
            "exceeded."
        ),
    )
    max_retries: int = Field(
        default=2,
        ge=0,
        description=(
            "Per-step retry budget applied when a step raises a "
            "retryable error. Steps may override per-step."
        ),
    )
    retry_backoff: Literal["exponential", "linear", "none"] = Field(
        default="exponential",
        description="Backoff policy between retries.",
    )
    concurrency: Literal[
        "drop_if_running", "queue", "always"
    ] = Field(
        default="drop_if_running",
        description=(
            "Behaviour when a new fire arrives while a previous run "
            "is still in progress. ``drop_if_running`` skips the new "
            "fire, ``queue`` enqueues it, ``always`` runs it in "
            "parallel."
        ),
    )
    budget_cap_usd: float | None = Field(
        default=None,
        gt=0,
        description=(
            "Optional mid-flight cost cap in USD. The executor kills "
            "the run when accumulated cost exceeds this value. v1 "
            "treats this as an advisory because cost tracking lands "
            "with the executor in a later step."
        ),
    )
    on_failure: list[PlanStep] = Field(
        default_factory=list,
        description=(
            "Secondary plan executed only when the main plan fails "
            "after retries exhaust. Empty list means no fallback."
        ),
    )
