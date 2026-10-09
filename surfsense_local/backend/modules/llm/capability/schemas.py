"""What the screens are told of a model's capability."""

from pydantic import BaseModel

from modules.llm.capability.level import Level
from modules.llm.capability.modes import ChatMode


class ReasonRead(BaseModel):
    # Rendered by the ICU catalogs: `measured_pass`, `measured_near`,
    # `measured_fail`, `assumed`, `measured_elsewhere`, `alias` or `no_row`.
    code: str
    values: dict[str, str | int] = {}


class MeasuredRead(BaseModel):
    """The row the level came from, for the evidence line."""

    key: str
    # `create-and-edit`, the ladder's 8 cases; `openrouter-screen`, its 2-case
    # screening; or `assumed`, a flagship not run.
    suite: str
    assumed: bool
    suite_version: int
    measured_on: str
    provider: str
    host: str
    reads_images: bool
    passed: int
    counted: int
    provisional: bool


class ModesRead(BaseModel):
    """What a new chat on this model may be, for the composer's mode switch."""

    agentic_allowed: bool
    # Why not, when not: `agent_not_installed`, `tool_calls_unsupported` or
    # `window_below_floor`. A score never blocks.
    blocked: str | None = None
    default_mode: ChatMode
    # What the switch says beside Agentic: `measured_pass`, `measured_near` or
    # `measured_below` with `passed` and `counted`; `local_copy` with `host`;
    # `assumed`; `untested`.
    reason: ReasonRead
    remembered_mode: ChatMode | None = None


class CapabilityRead(BaseModel):
    level: Level
    # The ICU select branch the short label is chosen by.
    label_key: str
    reason: ReasonRead
    # One line on what decided the level, in English, as the list ships it.
    note: str | None = None
    measured: MeasuredRead | None = None
    modes: ModesRead
