from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    ChatVisibility,
    NewChatMessage,
    NewChatMessageRole,
    NewChatThread,
    User,
    Workspace,
)
from app.tasks.chat.persistence import load_assistant_message_for_turn
from app.tasks.chat.streaming.flows.resume_chat.assistant_shell import (
    _resumable_journal_from_content,
)
from app.tasks.chat.streaming.handlers.tools.activity import resolve_tool_activity

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_old_paused_turn_restores_two_same_kind_tools_by_exact_call_id(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
) -> None:
    thread = NewChatThread(
        title="Resume identity",
        workspace_id=db_workspace.id,
        created_by_id=db_user.id,
        visibility=ChatVisibility.PRIVATE,
    )
    db_session.add(thread)
    await db_session.flush()

    spec = resolve_tool_activity("write_file", subagent_type=None)
    first = spec.snapshot(
        activity_id="act-first",
        sequence=1,
        status="awaiting_approval",
        started_at="2026-01-01T00:00:00+00:00",
    )
    second = spec.snapshot(
        activity_id="act-second",
        sequence=2,
        status="awaiting_approval",
        started_at="2026-01-01T00:00:01+00:00",
    )
    paused = NewChatMessage(
        thread_id=thread.id,
        role=NewChatMessageRole.ASSISTANT,
        turn_id="paused-turn",
        content=[
            {
                "type": "data-activities",
                "data": {
                    "activities": [first, second],
                    "timing": {"status": "paused", "activeDurationMs": 1200},
                },
            },
            {
                "type": "tool-call",
                "toolCallId": "ui-first",
                "langchainToolCallId": "lc-first",
                "toolName": "write_file",
                "metadata": {"activityId": first["id"]},
            },
            {
                "type": "tool-call",
                "toolCallId": "ui-second",
                "langchainToolCallId": "lc-second",
                "toolName": "write_file",
                "metadata": {"activityId": second["id"]},
            },
        ],
    )
    newer = [
        NewChatMessage(
            thread_id=thread.id,
            role=NewChatMessageRole.ASSISTANT,
            turn_id=f"newer-turn-{index}",
            content=[{"type": "text", "text": "newer"}],
        )
        for index in range(25)
    ]
    db_session.add_all([paused, *newer])
    await db_session.flush()

    resolved = await load_assistant_message_for_turn(
        db_session,
        chat_id=thread.id,
        turn_id="paused-turn",
    )
    assert resolved is not None
    journal = _resumable_journal_from_content(resolved.content)

    assert resolved.id == paused.id
    assert [activity["id"] for activity in journal.activities] == [
        "act-first",
        "act-second",
    ]
    assert journal.activity_id_by_tool_call == {
        "lc-first": "act-first",
        "ui-first": "act-first",
        "lc-second": "act-second",
        "ui-second": "act-second",
    }
