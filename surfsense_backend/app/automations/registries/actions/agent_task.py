"""Built-in ``agent_task`` action. Self-registers at import time."""

from __future__ import annotations

from typing import Any

from app.automations.schemas.actions import AgentTaskActionParams

from .store import register_action
from .types import ActionContext, ActionDefinition, ActionHandler


def _build_handler(ctx: ActionContext) -> ActionHandler:
    """Bind run/session context to the agent_task handler. Real wiring lands in Phase 4b."""
    del ctx  # ignored by the stub; real handler will consume it

    async def handle(params: dict[str, Any]) -> dict[str, Any]:
        AgentTaskActionParams.model_validate(params)
        return {"status": "stubbed"}

    return handle


AGENT_TASK_ACTION = ActionDefinition(
    type="agent_task",
    name="Agent task",
    description="Run an agent task with a scoped tool allowlist.",
    params_schema=AgentTaskActionParams.model_json_schema(),
    build_handler=_build_handler,
)

register_action(AGENT_TASK_ACTION)
