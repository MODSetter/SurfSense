"""Bind ``ActionContext`` to a callable that runs one ``agent_task`` step."""

from __future__ import annotations

from typing import Any

from app.automations.registries.actions.types import (
    ActionContext,
    ActionHandler,
)
from app.automations.schemas.actions import AgentTaskActionParams

from .invoke import run_agent_task


def build_handler(ctx: ActionContext) -> ActionHandler:
    """Return a handler closure that validates params and runs the agent task."""

    async def handle(params: dict[str, Any]) -> dict[str, Any]:
        validated = AgentTaskActionParams.model_validate(params)
        return await run_agent_task(
            ctx=ctx,
            query=validated.query,
            auto_approve_all=validated.auto_approve_all,
        )

    return handle
