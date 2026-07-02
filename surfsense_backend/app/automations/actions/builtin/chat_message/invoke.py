"""Run one ``chat_message`` step by draining ``stream_new_chat``.

Reuses the interactive chat turn: it persists the messages and advances the
durable checkpointer for the thread, so a scheduled tick shares the same
conversation memory as a user turn. The SSE frames have no client, so drain them.
"""

from __future__ import annotations

from typing import Any

from app.auth.context import AuthContext
from app.db import ChatVisibility, User
from app.services.chat_session_state_service import get_session_state
from app.tasks.chat.streaming.flows.new_chat.orchestrator import stream_new_chat

from ...types import ActionContext


async def run_chat_message(
    *,
    ctx: ActionContext,
    thread_id: int,
    message: str,
) -> dict[str, Any]:
    """Post ``message`` into ``thread_id`` and run one durable agent turn.

    Skips when a turn is already in flight on the thread, so a slow tick can't
    overlap the next scheduled fire.
    """
    state = await get_session_state(ctx.session, thread_id)
    if state is not None and state.ai_responding_to_user_id is not None:
        return {"thread_id": thread_id, "frames": 0, "skipped": "in_flight"}

    user_id = str(ctx.creator_user_id) if ctx.creator_user_id else None
    auth_context: AuthContext | None = None
    if ctx.creator_user_id:
        user = await ctx.session.get(User, ctx.creator_user_id)
        if user is not None:
            auth_context = AuthContext.system(user, source="automation")

    llm_config_id = ctx.chat_model_id if ctx.chat_model_id is not None else -1
    request_id = f"automation:{ctx.run_id}:{ctx.step_id}"

    frames = 0
    async for _sse in stream_new_chat(
        user_query=message,
        workspace_id=ctx.workspace_id,
        chat_id=thread_id,
        user_id=user_id,
        llm_config_id=llm_config_id,
        needs_history_bootstrap=False,
        thread_visibility=ChatVisibility.PRIVATE,
        auth_context=auth_context,
        request_id=request_id,
    ):
        frames += 1

    return {"thread_id": thread_id, "frames": frames, "skipped": None}
