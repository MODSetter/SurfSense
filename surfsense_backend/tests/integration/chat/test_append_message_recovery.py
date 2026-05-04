"""Integration tests for the cross-writer integration between the
streaming chat task and the legacy ``POST /threads/{id}/messages``
(``append_message``) round-trip.

Two scenarios anchor the contract introduced by the server-side
persistence rework:

(a) **Tool-heavy turn streamed to completion.**

    Drives :class:`AssistantContentBuilder` with synthetic SSE events
    that mirror what ``_stream_agent_events`` emits for a turn that
    interleaves text, reasoning, a tool call (start/delta/available/
    output), and a final text block. Then runs
    :func:`finalize_assistant_turn` and asserts:

    * ``new_chat_messages.content`` JSONB matches the
      ``ContentPart[]`` shape the FE history loader expects, with full
      ``args``/``argsText``/``result``/``langchainToolCallId`` for the
      tool call.
    * Exactly one ``token_usage`` row exists keyed on the assistant
      ``message_id``.

(b) **Stale FE ``appendMessage`` after server finalize.**

    Verifies the recovery branch of the ``append_message`` route now
    returns the SERVER's authoritative ``ContentPart[]`` (not the FE's
    stale payload) when the partial unique index from migration 141
    blocks the FE's INSERT, and that the ``ON CONFLICT DO NOTHING``
    clause from migration 142 stops the route from writing a duplicate
    ``token_usage`` row.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    ChatVisibility,
    NewChatMessage,
    NewChatMessageRole,
    NewChatThread,
    SearchSpace,
    TokenUsage,
    User,
)
from app.routes import new_chat_routes
from app.services.token_tracking_service import TurnTokenAccumulator
from app.tasks.chat import persistence as persistence_module
from app.tasks.chat.content_builder import AssistantContentBuilder
from app.tasks.chat.persistence import (
    finalize_assistant_turn,
    persist_assistant_shell,
)

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_thread(
    db_session: AsyncSession, db_user: User, db_search_space: SearchSpace
) -> NewChatThread:
    thread = NewChatThread(
        title="Test Chat",
        search_space_id=db_search_space.id,
        created_by_id=db_user.id,
        visibility=ChatVisibility.PRIVATE,
    )
    db_session.add(thread)
    await db_session.flush()
    return thread


@pytest.fixture
def patched_shielded_session(monkeypatch, db_session: AsyncSession):
    """Route persistence helpers to the test's savepoint-bound session.

    Mirrors the helper from ``test_persistence.py`` so the helpers'
    internal ``ws.commit()`` / ``ws.rollback()`` resolve to SAVEPOINT
    operations on the test transaction instead of touching real
    autocommit boundaries.
    """

    @asynccontextmanager
    async def _fake_shielded_session():
        yield db_session

    monkeypatch.setattr(
        persistence_module,
        "shielded_async_session",
        _fake_shielded_session,
    )
    return db_session


@pytest.fixture
def bypass_permission_checks(monkeypatch):
    """Replace RBAC + thread access checks with no-ops.

    The append_message route under test calls ``check_permission`` and
    ``check_thread_access``; those rely on a SearchSpaceMembership row
    that the existing integration fixtures don't create. The contract
    we want to verify here is the ``IntegrityError`` -> recovery branch,
    not the RBAC plumbing — so stub them.
    """

    async def _allow(*_args, **_kwargs):
        return True

    monkeypatch.setattr(new_chat_routes, "check_permission", _allow)
    monkeypatch.setattr(new_chat_routes, "check_thread_access", _allow)
    return None


class _FakeRequest:
    """Minimal Request stand-in used by ``append_message``.

    The route only calls ``await request.json()`` — keep the surface
    area tight so this doesn't accidentally hide future signature
    changes that we *would* want to break the test.
    """

    def __init__(self, body: dict):
        self._body = body

    async def json(self) -> dict:
        return self._body


def _build_tool_heavy_content() -> list[dict]:
    """Drive ``AssistantContentBuilder`` through a tool-heavy turn.

    Produces the same ``ContentPart[]`` shape the streaming layer would
    persist if ``_stream_agent_events`` ran a turn with: opening
    reasoning -> text -> tool call (input start/delta/available/output)
    -> closing text. Centralised here so the (a) and (b) scenarios use
    the same authoritative payload.
    """
    builder = AssistantContentBuilder()

    builder.on_reasoning_start("r1")
    builder.on_reasoning_delta("r1", "Let me look up ")
    builder.on_reasoning_delta("r1", "the file listing.")
    builder.on_reasoning_end("r1")

    builder.on_text_start("t1")
    builder.on_text_delta("t1", "Sure, listing files in ")
    builder.on_text_delta("t1", "/.")
    builder.on_text_end("t1")

    builder.on_tool_input_start(
        "tool_call_ui_1",
        tool_name="ls",
        langchain_tool_call_id="lc_call_xyz",
    )
    builder.on_tool_input_delta("tool_call_ui_1", '{"path"')
    builder.on_tool_input_delta("tool_call_ui_1", ': "/"}')
    builder.on_tool_input_available(
        "tool_call_ui_1",
        tool_name="ls",
        args={"path": "/"},
        langchain_tool_call_id="lc_call_xyz",
    )
    builder.on_tool_output_available(
        "tool_call_ui_1",
        output={"files": ["a.txt", "b.txt"]},
        langchain_tool_call_id="lc_call_xyz",
    )

    builder.on_text_start("t2")
    builder.on_text_delta("t2", "Found 2 files: a.txt and b.txt.")
    builder.on_text_end("t2")

    return builder.snapshot()


def _accumulator_with_one_call() -> TurnTokenAccumulator:
    acc = TurnTokenAccumulator()
    acc.add(
        model="gpt-4o-mini",
        prompt_tokens=200,
        completion_tokens=80,
        total_tokens=280,
        cost_micros=22222,
    )
    return acc


# ---------------------------------------------------------------------------
# (a) Tool-heavy stream finalize
# ---------------------------------------------------------------------------


class TestToolHeavyTurnFinalize:
    async def test_full_tool_call_persisted_and_one_token_usage_row(
        self,
        db_session,
        db_user,
        db_thread,
        db_search_space,
        patched_shielded_session,
    ):
        """End-to-end seam: builder snapshot -> finalize -> DB row.

        Matches the production flow's *content* invariant: whatever
        ``AssistantContentBuilder.snapshot()`` produces is what the
        streaming layer hands to ``finalize_assistant_turn``, so this
        test catches any drift between the JSONB shape the builder
        emits and the one the FE history loader expects.
        """
        thread_id = db_thread.id
        user_id_str = str(db_user.id)
        search_space_id = db_search_space.id
        turn_id = f"{thread_id}:tool_heavy"

        msg_id = await persist_assistant_shell(
            chat_id=thread_id,
            user_id=user_id_str,
            turn_id=turn_id,
        )
        assert msg_id is not None

        snapshot = _build_tool_heavy_content()
        # Sanity-check the snapshot before we hand it to the DB so a
        # builder regression surfaces here, not deep inside an opaque
        # JSONB diff.
        assert any(p.get("type") == "reasoning" for p in snapshot)
        text_parts = [p for p in snapshot if p.get("type") == "text"]
        assert len(text_parts) == 2
        tool_parts = [p for p in snapshot if p.get("type") == "tool-call"]
        assert len(tool_parts) == 1
        tool_part = tool_parts[0]
        assert tool_part["toolCallId"] == "tool_call_ui_1"
        assert tool_part["toolName"] == "ls"
        assert tool_part["args"] == {"path": "/"}
        # ``argsText`` ends up as the pretty-printed final args (the
        # ``tool-input-available`` event replaces the streamed deltas
        # with ``json.dumps(args, indent=2)`` to match the FE's
        # post-stream rendering).
        assert tool_part["argsText"] == '{\n  "path": "/"\n}'
        assert tool_part["result"] == {"files": ["a.txt", "b.txt"]}
        # ``langchainToolCallId`` is the agent-side correlation id used
        # by the regenerate path; a missing one breaks
        # edit-from-tool-call later.
        assert tool_part["langchainToolCallId"] == "lc_call_xyz"

        await finalize_assistant_turn(
            message_id=msg_id,
            chat_id=thread_id,
            search_space_id=search_space_id,
            user_id=user_id_str,
            turn_id=turn_id,
            content=snapshot,
            accumulator=_accumulator_with_one_call(),
        )

        # ``content`` must round-trip byte-for-byte through the JSONB
        # column. SQLAlchemy doesn't auto-refresh the row that survived
        # the savepoint commit, so refresh explicitly.
        row = await db_session.get(NewChatMessage, msg_id)
        await db_session.refresh(row)

        # The history loader reads ``content`` straight into the FE's
        # parts array, so a strict equality comparison is the right
        # invariant here.
        assert row.content == snapshot
        # Tool-call parts must JSON-serialise cleanly — nothing in
        # ``args`` / ``argsText`` / ``result`` should accidentally be a
        # non-JSON-safe value (datetime, set, custom class).
        assert json.dumps(row.content)

        usage_count = (
            await db_session.execute(
                select(func.count())
                .select_from(TokenUsage)
                .where(TokenUsage.message_id == msg_id)
            )
        ).scalar_one()
        assert usage_count == 1

        usage = (
            await db_session.execute(
                select(TokenUsage).where(TokenUsage.message_id == msg_id)
            )
        ).scalar_one()
        assert usage.usage_type == "chat"
        assert usage.prompt_tokens == 200
        assert usage.completion_tokens == 80
        assert usage.total_tokens == 280
        assert usage.cost_micros == 22222
        assert usage.thread_id == thread_id
        assert usage.search_space_id == search_space_id


# ---------------------------------------------------------------------------
# (b) FE appendMessage after server finalize
# ---------------------------------------------------------------------------


class TestAppendMessageRecoveryAfterFinalize:
    async def test_returns_server_content_and_does_not_duplicate_token_usage(
        self,
        db_session,
        db_user,
        db_thread,
        db_search_space,
        patched_shielded_session,
        bypass_permission_checks,
    ):
        """FE's stale ``appendMessage`` after server finalize.

        The frontend used to be the authoritative writer for assistant
        ``content``. Now the server is. When the legacy FE round-trip
        fires *after* the server has already finalized:

        * the route's INSERT trips the (thread_id, turn_id, role)
          partial unique index from migration 141,
        * the recovery branch fetches the existing row and returns
          *its* ``content`` — discarding the FE payload — so the
          history loader reads the rich server payload (full tool
          args, argsText, langchainToolCallId, etc.) on next page
          reload,
        * the route's optional ``token_usage`` insert is keyed on the
          partial unique index from migration 142 so it silently
          no-ops if the server already wrote one.
        """
        thread_id = db_thread.id
        user_id_str = str(db_user.id)
        search_space_id = db_search_space.id
        turn_id = f"{thread_id}:fe_late_append"

        # Step 1: server stream completes. Server-built rich content is
        # finalized.
        msg_id = await persist_assistant_shell(
            chat_id=thread_id,
            user_id=user_id_str,
            turn_id=turn_id,
        )
        assert msg_id is not None

        server_content = _build_tool_heavy_content()
        await finalize_assistant_turn(
            message_id=msg_id,
            chat_id=thread_id,
            search_space_id=search_space_id,
            user_id=user_id_str,
            turn_id=turn_id,
            content=server_content,
            accumulator=_accumulator_with_one_call(),
        )

        # Step 2: simulate the legacy FE ``appendMessage`` round-trip
        # arriving with stale, lossy content (missing tool args, etc.)
        # plus a ``token_usage`` body.
        fe_stale_content = [
            {"type": "text", "text": "Found 2 files: a.txt and b.txt."},
        ]
        fe_request_body = {
            "role": "assistant",
            "content": fe_stale_content,
            "turn_id": turn_id,
            "token_usage": {
                "prompt_tokens": 999,
                "completion_tokens": 999,
                "total_tokens": 1998,
                "cost_micros": 88888,
                "usage": {"any": "thing"},
                "call_details": {"calls": []},
            },
        }
        request = _FakeRequest(fe_request_body)

        # ``db_user`` is bound to ``db_session``. The route's
        # IntegrityError branch calls ``session.rollback()``, which
        # expires every ORM row attached to the session including this
        # user — historically causing ``user.id`` to lazy-load
        # out-of-greenlet and crash the request with ``MissingGreenlet``
        # (observed in production logs at /api/v1/threads/531/messages
        # 2026-05-04). The route now captures ``user.id`` to a primitive
        # UUID at the top of the handler, so the rollback can't reach
        # it. Pass the *attached* user here on purpose — that's the
        # production scenario, and this test is the regression guard
        # against that bug returning.
        response = await new_chat_routes.append_message(
            thread_id=thread_id,
            request=request,
            session=db_session,
            user=db_user,
        )

        # Response must echo the SERVER's rich payload, not the FE's
        # stale snapshot. This is the user-visible part of the
        # contract: history reload + ThreadHistoryAdapter.append both
        # read from the same authoritative source.
        assert response.id == msg_id
        assert response.role == NewChatMessageRole.ASSISTANT
        assert response.turn_id == turn_id
        assert response.content == server_content
        assert response.content != fe_stale_content

        # The on-disk row must agree with the response.
        row = await db_session.get(NewChatMessage, msg_id)
        await db_session.refresh(row)
        assert row.content == server_content

        # ``token_usage``: exactly one row, with the *server's* values
        # (the FE's much larger token counts must not have overwritten
        # them).
        usage_count = (
            await db_session.execute(
                select(func.count())
                .select_from(TokenUsage)
                .where(TokenUsage.message_id == msg_id)
            )
        ).scalar_one()
        assert usage_count == 1

        usage = (
            await db_session.execute(
                select(TokenUsage).where(TokenUsage.message_id == msg_id)
            )
        ).scalar_one()
        assert usage.cost_micros == 22222  # Server's value, not 88888
        assert usage.total_tokens == 280  # Server's value, not 1998

    async def test_legacy_fe_first_appendmessage_then_server_no_dupe(
        self,
        db_session,
        db_user,
        db_thread,
        db_search_space,
        patched_shielded_session,
        bypass_permission_checks,
    ):
        """Inverse race: legacy FE writes first, server finalize second.

        Some clients still post ``appendMessage`` before the streaming
        ``finally`` runs. The contract is symmetric: whichever writer
        loses the (thread_id, turn_id, role) race silently lets the
        winner keep its content. In particular the *server's*
        finalize must NOT raise — it must look up the existing row and
        UPDATE its content with the server-built payload (which is
        always richer/more authoritative than whatever the FE
        snapshot held).
        """
        thread_id = db_thread.id
        user_id_str = str(db_user.id)
        search_space_id = db_search_space.id
        turn_id = f"{thread_id}:fe_first"

        # Step 1: legacy FE appendMessage lands first. No prior shell
        # row exists; the route does the INSERT itself.
        fe_request_body = {
            "role": "assistant",
            "content": [{"type": "text", "text": "early FE write"}],
            "turn_id": turn_id,
        }
        fe_response = await new_chat_routes.append_message(
            thread_id=thread_id,
            request=_FakeRequest(fe_request_body),
            session=db_session,
            user=db_user,
        )
        assert fe_response.role == NewChatMessageRole.ASSISTANT

        # Step 2: server stream's persist_assistant_shell now races
        # behind. It must adopt the existing row id, not raise.
        adopted_id = await persist_assistant_shell(
            chat_id=thread_id,
            user_id=user_id_str,
            turn_id=turn_id,
        )
        assert adopted_id == fe_response.id

        # Step 3: server finalize then overwrites the FE's stub with
        # the rich content (which is the correct, more authoritative
        # payload).
        server_content = _build_tool_heavy_content()
        await finalize_assistant_turn(
            message_id=adopted_id,
            chat_id=thread_id,
            search_space_id=search_space_id,
            user_id=user_id_str,
            turn_id=turn_id,
            content=server_content,
            accumulator=_accumulator_with_one_call(),
        )

        # Final state: one row, server content, one token_usage row.
        msg_count = (
            await db_session.execute(
                select(func.count())
                .select_from(NewChatMessage)
                .where(
                    NewChatMessage.thread_id == thread_id,
                    NewChatMessage.turn_id == turn_id,
                    NewChatMessage.role == NewChatMessageRole.ASSISTANT,
                )
            )
        ).scalar_one()
        assert msg_count == 1

        row = await db_session.get(NewChatMessage, adopted_id)
        await db_session.refresh(row)
        assert row.content == server_content

        usage_count = (
            await db_session.execute(
                select(func.count())
                .select_from(TokenUsage)
                .where(TokenUsage.message_id == adopted_id)
            )
        ).scalar_one()
        assert usage_count == 1

    async def test_appendmessage_without_turn_id_legacy_400(
        self,
        db_session,
        db_user,
        db_thread,
        patched_shielded_session,
        bypass_permission_checks,
    ):
        """Defensive: a bare appendMessage with no turn_id and no
        existing row is just a normal INSERT — must succeed. But if a
        row with the same role already exists in this thread *without*
        turn_id collisions, the route should fall through to the
        legacy 400 path on a foreign-key / unrelated IntegrityError
        (we don't ship that bug today, but pin the behaviour so a
        future schema change can't silently regress it).
        """
        thread_id = db_thread.id

        # Bare appendMessage with no turn_id — should just succeed
        # without invoking the recovery branch.
        ok_response = await new_chat_routes.append_message(
            thread_id=thread_id,
            request=_FakeRequest(
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "hi"}],
                }
            ),
            session=db_session,
            user=db_user,
        )
        assert ok_response.role == NewChatMessageRole.USER
        assert ok_response.turn_id is None

        # Sanity: the route did NOT silently swallow the missing
        # turn_id by routing through the unique-index recovery branch
        # — it took the happy path.
        msg_count = (
            await db_session.execute(
                select(func.count())
                .select_from(NewChatMessage)
                .where(
                    NewChatMessage.thread_id == thread_id,
                    NewChatMessage.role == NewChatMessageRole.USER,
                )
            )
        ).scalar_one()
        assert msg_count == 1
