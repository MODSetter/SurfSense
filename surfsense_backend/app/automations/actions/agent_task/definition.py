"""``agent_task`` ``ActionDefinition`` registration."""

from __future__ import annotations

from ..store import register_action
from ..types import ActionDefinition
from .factory import build_handler
from .params import AgentTaskActionParams

AGENT_TASK_ACTION = ActionDefinition(
    type="agent_task",
    name="Agent task",
    description="Run a multi_agent_chat turn from an automation step.",
    params_model=AgentTaskActionParams,
    build_handler=build_handler,
)

register_action(AGENT_TASK_ACTION)
