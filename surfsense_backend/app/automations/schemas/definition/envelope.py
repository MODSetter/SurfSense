"""``AutomationDefinition`` — the top-level envelope persisted in ``automations.definition``."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .execution import ExecutionBlock
from .inputs import InputsBlock
from .metadata import MetadataBlock
from .plan_step import PlanStep
from .trigger_spec import TriggerSpec


class AutomationDefinition(BaseModel):
    """The top-level JSON shape stored in ``automations.definition``.

    This is the editable spec a user authors (or the NL generator
    produces). The envelope is structural only — every nested
    discriminator (``triggers[].type``, ``plan[].action``) is resolved
    against the registries at validation time, so adding a new
    trigger or action type does not require touching this schema.

    See ``automation-design-plan.md`` §5 for the worked example and
    rationale.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="1.0",
        description=(
            "Schema version of the envelope itself. Migrations bump "
            "this when the envelope shape changes; nested per-type "
            "configs evolve independently via the registries."
        ),
    )
    name: str = Field(
        ...,
        description="Short, user-facing name shown in lists.",
        min_length=1,
        max_length=200,
    )
    goal: str | None = Field(
        default=None,
        description=(
            "Optional plain-language statement of what the "
            "automation is for. Used by the NL generator's review "
            "pass and by the UI's run dialog."
        ),
    )
    inputs: InputsBlock | None = Field(
        default=None,
        description=(
            "Optional input contract. When omitted, the automation "
            "accepts no inputs at fire time."
        ),
    )
    triggers: list[TriggerSpec] = Field(
        default_factory=list,
        description=(
            "Triggers that fire this automation. Empty list means "
            "the automation is only runnable via the manual "
            "``Run now`` path."
        ),
    )
    plan: list[PlanStep] = Field(
        ...,
        description=(
            "Ordered sequence of steps. Executed in array order — "
            "no parallelism, no DAGs, no loops at the envelope "
            "level."
        ),
        min_length=1,
    )
    execution: ExecutionBlock = Field(
        default_factory=ExecutionBlock,
        description=(
            "Execution defaults (timeouts, retries, concurrency, "
            "budget). All fields default to safe values; the block "
            "may be omitted entirely."
        ),
    )
    metadata: MetadataBlock = Field(
        default_factory=MetadataBlock,
        description=(
            "Free-form metadata (tags, NL-generator breadcrumbs, "
            "UI annotations). Tolerates unknown keys by design."
        ),
    )
