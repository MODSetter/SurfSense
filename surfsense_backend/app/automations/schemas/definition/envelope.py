"""``AutomationDefinition`` — top-level envelope persisted in ``automations.definition``."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .execution import ExecutionBlock
from .inputs import InputsBlock
from .metadata import MetadataBlock
from .plan_step import PlanStep
from .trigger_spec import TriggerSpec


class AutomationDefinition(BaseModel):
    """Top-level shape of an automation."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    name: str = Field(..., min_length=1, max_length=200)
    goal: str | None = None
    inputs: InputsBlock | None = None
    triggers: list[TriggerSpec] = Field(default_factory=list)
    plan: list[PlanStep] = Field(..., min_length=1)
    execution: ExecutionBlock = Field(default_factory=ExecutionBlock)
    metadata: MetadataBlock = Field(default_factory=MetadataBlock)
