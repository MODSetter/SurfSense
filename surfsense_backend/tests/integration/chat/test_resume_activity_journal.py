from __future__ import annotations

from types import SimpleNamespace

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
from app.services.new_streaming_service import VercelStreamingService
from app.tasks.chat.content_builder import AssistantContentBuilder
from app.tasks.chat.persistence import load_assistant_message_for_turn
from app.tasks.chat.streaming.flows.resume_chat.assistant_shell import (
    _resumable_journal_from_content,
    order_resume_tool_call_ids,
)
from app.tasks.chat.streaming.handlers.tool_start import iter_tool_start_frames
from app.tasks.chat.streaming.handlers.tools.activity import resolve_tool_activity
from app.tasks.chat.streaming.relay.state import AgentEventRelayState

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
    assert journal.tool_call_ids == ["lc-first", "lc-second"]
    assert order_resume_tool_call_ids(journal, ["ui-second", "ui-first"]) == [
        "lc-second",
        "lc-first",
    ]

    relay_state = AgentEventRelayState.for_invocation(
        initial_activities=journal.activities,
        resume_activity_id_by_tool_call=journal.activity_id_by_tool_call,
        resume_tool_call_ids=journal.tool_call_ids,
    )
    builder = AssistantContentBuilder()
    for run_id in ("fresh-first", "fresh-second"):
        list(
            iter_tool_start_frames(
                {
                    "name": "write_file",
                    "run_id": run_id,
                    "data": {"input": {"file_path": f"{run_id}.md", "content": "x"}},
                },
                state=relay_state,
                streaming_service=VercelStreamingService(),
                content_builder=builder,
                result=SimpleNamespace(write_attempted=False),
                step_prefix="resume",
            )
        )

    assert relay_state.journal.id_by_run == {
        "fresh-first": "act-first",
        "fresh-second": "act-second",
    }
    assert not relay_state.resume_tool_call_ids
    assert not relay_state.journal.resume_id_by_tool_call
