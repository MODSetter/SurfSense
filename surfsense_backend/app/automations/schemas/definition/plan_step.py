"""``PlanStep`` — one entry in the envelope's ``plan`` array."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PlanStep(BaseModel):
    """One step in an automation's sequential plan.

    Steps run in array order, no parallelism, no DAGs, no loops. The
    ``when`` Jinja expression provides conditional skip; branching is
    achieved by ``when`` clauses on multiple steps. For looping or
    parallel work, the user routes through ``agent_task`` and lets the
    agent reason about it.

    ``config`` is dispatched against the action registry at
    validation time — its shape is determined by
    ``ActionDefinition.config_schema`` for the ``action`` value.

    ``output_as`` binds the step's typed output into the template
    namespace for later steps, e.g. ``output_as: 'summary'`` then
    ``{{ summary.bullets }}`` in a downstream step's config.
    """

    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(
        ...,
        description=(
            "Unique-within-plan identifier. Used in run logs and as "
            "the default for ``output_as`` when not provided."
        ),
        min_length=1,
    )
    action: str = Field(
        ...,
        description=(
            "Action-type discriminator (e.g., ``agent_task``). "
            "Resolved against the action registry."
        ),
        min_length=1,
    )
    when: str | None = Field(
        default=None,
        description=(
            "Optional Jinja expression evaluated against the run "
            "context. Step is skipped when the expression is "
            "falsy."
        ),
    )
    config: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Action-type-specific config. Validated against the "
            "registered ``ActionDefinition.config_schema`` for "
            "``action`` at definition-save time. Jinja templates "
            "inside config are rendered at step-execute time."
        ),
    )
    output_as: str | None = Field(
        default=None,
        description=(
            "Name to bind the step output under for downstream "
            "steps. Defaults to ``step_id`` when omitted."
        ),
    )
    max_retries: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Per-step override of the automation-level ``max_retries``. "
            "Omitted means inherit from execution block."
        ),
    )
    timeout_seconds: int | None = Field(
        default=None,
        gt=0,
        description=(
            "Per-step override of the automation-level "
            "``timeout_seconds``. Omitted means inherit from "
            "execution block."
        ),
    )
