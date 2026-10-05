"""What the screens are told of a model's capability."""

from pydantic import BaseModel

from modules.llm.capability.level import Level


class ReasonRead(BaseModel):
    # Rendered by the ICU catalogs: `measured_pass`, `measured_near`,
    # `measured_fail`, `measured_elsewhere`, `alias` or `no_row`.
    code: str
    values: dict[str, str | int] = {}


class MeasuredRead(BaseModel):
    """The row the level came from, for the evidence line."""

    key: str
    suite_version: int
    measured_on: str
    provider: str
    host: str
    reads_images: bool
    passed: int
    counted: int
    provisional: bool


class AgentTrialRead(BaseModel):
    # Only a model not measured is offered it, and only one that can carry the agent.
    offered: bool
    enabled: bool
    # `tool_calls_unconfirmed` or `window_below_floor` when it cannot be offered.
    blocked: str | None = None


class CapabilityRead(BaseModel):
    level: Level
    # The ICU select branch the short label is chosen by.
    label_key: str
    reason: ReasonRead
    # One line on what decided the level, in English, as the list ships it.
    note: str | None = None
    measured: MeasuredRead | None = None
    agent_trial: AgentTrialRead


class AgentTrialWrite(BaseModel):
    enabled: bool
