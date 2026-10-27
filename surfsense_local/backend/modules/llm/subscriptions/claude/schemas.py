from pydantic import BaseModel, Field

from modules.llm.model_type import ModelType
from modules.llm.subscriptions.claude.status import ClaudeState


class ClaudeHost(BaseModel):
    """A host the plan reaches that egress has not allowed yet."""

    destination: str
    host: str


class ClaudeOption(BaseModel):
    """Whether a slot offers a Claude plan, and the hosts still to allow; never runs Claude Code."""

    # The slots a Claude plan fills, from the one rule every picker reads.
    serves: list[ModelType]
    hosts: list[ClaudeHost]


class ClaudeStatusRead(BaseModel):
    """What the Claude plan dialog shows: Claude Code's state, read live."""

    state: ClaudeState
    version: str | None
    email: str | None
    plan: str | None
    # Claude Code is installed and signed in inside the container, not on the host.
    in_container: bool


class ClaudeConnectionWrite(BaseModel):
    label: str = Field(min_length=1, max_length=100)
