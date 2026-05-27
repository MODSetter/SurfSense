"""Built-in ``agent_task`` action. Self-registers at import time."""

from __future__ import annotations

from typing import Any

from app.automations.schemas.actions import AgentTaskActionParams

from .store import register_action
from .types import ActionDefinition


async def _handle_agent_task(args: dict[str, Any]) -> dict[str, Any]:
    """Stub. Validates params; real wiring lands with the executor."""
    AgentTaskActionParams.model_validate(args)
    return {"status": "stubbed"}


AGENT_TASK_ACTION = ActionDefinition(
    type="agent_task",
    name="Agent task",
    description="Run an agent task with a scoped tool allowlist.",
    params_schema=AgentTaskActionParams.model_json_schema(),
    handler=_handle_agent_task,
)

register_action(AGENT_TASK_ACTION)
