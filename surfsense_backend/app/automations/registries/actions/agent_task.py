"""Built-in ``agent_task`` action. Self-registers at import time."""

from __future__ import annotations

from app.automations.actions.agent_task import build_handler
from app.automations.schemas.actions import AgentTaskActionParams

from .store import register_action
from .types import ActionDefinition

AGENT_TASK_ACTION = ActionDefinition(
    type="agent_task",
    name="Agent task",
    description="Run a multi_agent_chat turn from an automation step.",
    params_schema=AgentTaskActionParams.model_json_schema(),
    build_handler=build_handler,
)

register_action(AGENT_TASK_ACTION)
