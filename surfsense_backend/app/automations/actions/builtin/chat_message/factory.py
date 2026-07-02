"""Bind ``ActionContext`` to a callable that runs one ``chat_message`` step."""

from __future__ import annotations

from typing import Any

from ...types import ActionContext, ActionHandler
from .invoke import run_chat_message
from .params import ChatMessageActionParams


def build_handler(ctx: ActionContext) -> ActionHandler:
    """Return a handler closure that validates params and posts the turn."""

    async def handle(params: dict[str, Any]) -> dict[str, Any]:
        validated = ChatMessageActionParams.model_validate(params)
        return await run_chat_message(
            ctx=ctx,
            thread_id=validated.thread_id,
            message=validated.message,
        )

    return handle
