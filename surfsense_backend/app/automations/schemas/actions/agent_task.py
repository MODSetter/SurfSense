"""``AgentTaskActionConfig`` — config for the ``agent_task`` action type."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentTaskActionConfig(BaseModel):
    """Run a LangGraph Deep Agent restricted to a scoped capability list."""

    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(..., min_length=1, description="Task prompt; Jinja-rendered.")
    tools: list[str] = Field(
        default_factory=list,
        description="Capability IDs the agent may call. Empty = no tool access.",
    )
    model: str | None = Field(
        default=None,
        description="LiteLLM model id. Defaults to the search space's agent_llm_id.",
    )
    output_schema: dict[str, Any] | None = Field(
        default=None,
        description="JSON Schema the agent must return. Recommended.",
    )
