"""``AgentTaskActionParams`` — params for the ``agent_task`` action type."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AgentTaskActionParams(BaseModel):
    """Run a multi_agent_chat turn from an automation step."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        ...,
        min_length=1,
        description="User query for the agent; rendered at execute time.",
    )
    auto_approve_all: bool = Field(
        default=False,
        description="If true, every HITL approval is auto-approved; otherwise rejected.",
    )
