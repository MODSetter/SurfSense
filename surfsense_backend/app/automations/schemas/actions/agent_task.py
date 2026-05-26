"""``AgentTaskActionConfig`` — config for the ``agent_task`` action type."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentTaskActionConfig(BaseModel):
    """Config for an ``agent_task`` plan step.

    Validated against ``PlanStep.config`` whenever the step's
    ``action`` is ``agent_task``. The step instructs the LangGraph
    Deep Agent runtime to:

    1. Receive ``prompt`` (with all preceding-step outputs and inputs
       already rendered by the template engine).
    2. Run the agent with access to *exactly* the capabilities named
       in ``tools`` — nothing else from the registry is visible to
       this agent invocation.
    3. Return a JSON object matching ``output_schema`` (recommended;
       the executor validates and re-prompts on mismatch).

    ``output_schema`` is the design's "dynamic output contract" —
    instead of locking the output shape on the ActionDefinition (as
    tight actions do), the user declares the shape they want for this
    specific step, and the agent has to match it.
    """

    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(
        ...,
        description=(
            "The task prompt rendered through the Jinja sandbox. May "
            "reference automation inputs and prior-step outputs."
        ),
        min_length=1,
    )
    tools: list[str] = Field(
        default_factory=list,
        description=(
            "Allowlist of capability IDs the agent may call (e.g., "
            "'search_space.query'). Empty list = no tool access; the "
            "agent must answer from the prompt alone."
        ),
    )
    model: str | None = Field(
        default=None,
        description=(
            "Optional LiteLLM model identifier (e.g., "
            "'anthropic/claude-sonnet-4-7'). Omitted means the "
            "automation falls back to the search space's default "
            "agent_llm_id."
        ),
    )
    output_schema: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Optional JSON Schema declaring the shape the agent must "
            "return. Strongly recommended; the editor warns when "
            "missing. Validated by the executor before binding to "
            "``output_as``."
        ),
    )
