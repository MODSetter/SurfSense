"""``AutomationDefinition`` — top-level envelope persisted in ``automations.definition``."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .execution import Execution
from .inputs import Inputs
from .metadata import Metadata
from .plan_step import PlanStep
from .trigger_spec import TriggerSpec


class AutomationModels(BaseModel):
    """Captured model profile for an automation.

    Snapshotted from the search space's model roles at create time so runs are
    insulated from later chat/search-space model changes. Model-id conventions
    match the shared scheme (``0`` Auto, ``< 0`` global, ``> 0`` BYOK).
    """

    model_config = ConfigDict(extra="forbid")

    chat_model_id: int = 0
    image_gen_model_id: int = 0
    vision_model_id: int = 0


class AutomationDefinition(BaseModel):
    """Top-level shape of an automation."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    name: str = Field(..., min_length=1, max_length=200)
    goal: str | None = None
    inputs: Inputs | None = None
    triggers: list[TriggerSpec] = Field(default_factory=list)
    plan: list[PlanStep] = Field(..., min_length=1)
    execution: Execution = Field(default_factory=Execution)
    metadata: Metadata = Field(default_factory=Metadata)
    # Captured server-side at create() and preserved across update(); resolved
    # at runtime instead of the live search space. Optional so drafts/builder
    # payloads validate without it.
    models: AutomationModels | None = None
