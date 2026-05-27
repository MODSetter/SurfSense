"""``AgentTaskActionParams`` — params for the ``agent_task`` action type."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentTaskActionParams(BaseModel):
    """Run an agent task with a scoped tool allowlist."""

    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(..., min_length=1, description="Task prompt; rendered at execute time.")
    tools: list[str] = Field(
        default_factory=list,
        description="Tool identifiers the agent may call. Empty = no tool access.",
    )
    model: str | None = Field(
        default=None,
        description="Model identifier. Defaults to the search space's agent_llm_id.",
    )
    output_schema: dict[str, Any] | None = Field(
        default=None,
        description="JSON Schema (draft 2020-12) the agent must return. Recommended.",
    )
