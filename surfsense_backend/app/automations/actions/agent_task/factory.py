"""Bind ``ActionContext`` to a callable that runs one ``agent_task`` step."""

from __future__ import annotations

from typing import Any

from ..types import ActionContext, ActionHandler
from .invoke import run_agent_task
from .params import AgentTaskActionParams


def build_handler(ctx: ActionContext) -> ActionHandler:
    """Return a handler closure that validates params and runs the agent task."""

    async def handle(params: dict[str, Any]) -> dict[str, Any]:
        validated = AgentTaskActionParams.model_validate(params)
        return await run_agent_task(
            ctx=ctx,
            query=validated.query,
            auto_approve_all=validated.auto_approve_all,
            mentioned_document_ids=validated.mentioned_document_ids,
            mentioned_folder_ids=validated.mentioned_folder_ids,
            mentioned_connector_ids=validated.mentioned_connector_ids,
            mentioned_connectors=validated.mentioned_connectors,
            mentioned_documents=validated.mentioned_documents,
        )

    return handle
