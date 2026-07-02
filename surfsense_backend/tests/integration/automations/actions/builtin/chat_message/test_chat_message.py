"""Integration tests for the ``chat_message`` action's concurrency guard.

The guard reads real ``ChatSessionState`` (seeded via the production
``set_ai_responding`` helper) to decide whether a scheduled watch tick may run.
This proves the skip decision against real persistence — the part a fake
``get_session_state`` could silently get wrong.

The turn's actual work (``stream_new_chat``) resolves an LLM from the DB and
runs the agent; that end-to-end drain is a running-stack concern. Here it is
replaced by a spy so we can assert the guard's two outcomes: skip without
streaming when a turn is in flight, and stream (with system auth) when not.
"""

from __future__ import annotations

from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.automations.actions.builtin.chat_message import invoke as invoke_mod
from app.automations.actions.types import ActionContext
from app.db import ChatVisibility, NewChatThread, User, Workspace
from app.services.chat_session_state_service import (
    clear_ai_responding,
    set_ai_responding,
)

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def thread(
    db_session: AsyncSession, db_user: User, db_workspace: Workspace
) -> NewChatThread:
    row = NewChatThread(
        title="Watched chat",
        workspace_id=db_workspace.id,
        created_by_id=db_user.id,
        visibility=ChatVisibility.PRIVATE,
    )
    db_session.add(row)
    await db_session.flush()
    return row


def _ctx(session: AsyncSession, *, workspace_id: int, creator_id) -> ActionContext:
    return ActionContext(
        session=session,
        run_id=1,
        step_id="watch",
        workspace_id=workspace_id,
        creator_user_id=creator_id,
        chat_model_id=1,
    )


async def test_skips_without_streaming_when_a_turn_is_in_flight(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
    thread: NewChatThread,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await set_ai_responding(db_session, thread.id, db_user.id)

    streamed = {"called": False}

    async def _spy(**_kwargs: Any):
        streamed["called"] = True
        yield "data: x\n\n"

    monkeypatch.setattr(invoke_mod, "stream_new_chat", _spy)

    out = await invoke_mod.run_chat_message(
        ctx=_ctx(db_session, workspace_id=db_workspace.id, creator_id=db_user.id),
        thread_id=thread.id,
        message="tick",
    )

    assert out["skipped"] == "in_flight"
    assert out["frames"] == 0
    assert streamed["called"] is False


async def test_streams_under_system_auth_when_no_turn_in_flight(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
    thread: NewChatThread,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Ensure the thread has no in-flight turn.
    await clear_ai_responding(db_session, thread.id)

    captured: dict[str, Any] = {}

    async def _spy(**kwargs: Any):
        captured.update(kwargs)
        for frame in ("data: a\n\n", "data: b\n\n"):
            yield frame

    monkeypatch.setattr(invoke_mod, "stream_new_chat", _spy)

    out = await invoke_mod.run_chat_message(
        ctx=_ctx(db_session, workspace_id=db_workspace.id, creator_id=db_user.id),
        thread_id=thread.id,
        message="what changed?",
    )

    assert out["skipped"] is None
    assert out["frames"] == 2
    assert captured["chat_id"] == thread.id
    assert captured["user_query"] == "what changed?"
    assert captured["user_id"] == str(db_user.id)
    auth = captured["auth_context"]
    assert auth is not None and auth.method == "system" and auth.source == "automation"
