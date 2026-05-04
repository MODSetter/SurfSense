"""Integration tests for ``app.tasks.chat.persistence``.

Verifies the DB-side guarantees the streaming chat task relies on:

* ``persist_assistant_shell`` is idempotent against the
  ``(thread_id, turn_id, ASSISTANT)`` partial unique index from
  migration 141. Two calls with the same ``turn_id`` return the SAME
  ``message_id`` and never create a duplicate ``new_chat_messages`` row.
* ``finalize_assistant_turn`` writes a status-marker payload when given
  empty content, never raises, and is safe to call twice on the same
  ``message_id`` — the partial unique index from migration 142
  (``uq_token_usage_message_id``) prevents the second insert from
  producing a duplicate ``token_usage`` row.
* The same ``ON CONFLICT DO NOTHING`` invariant covers the cross-writer
  race where ``finalize_assistant_turn`` and the ``append_message``
  recovery branch both target the same ``message_id``.

All tests run inside the conftest's outer-transaction-with-savepoint
fixture so commits inside the helpers (which open their own
``shielded_async_session``) are released as savepoints and rolled back
at test end. We monkey-patch ``shielded_async_session`` to yield the
same pooled test session so the integration transaction stays
in-scope.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
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
from app.services.token_tracking_service import TurnTokenAccumulator
from app.tasks.chat import persistence as persistence_module
from app.tasks.chat.persistence import (
    finalize_assistant_turn,
    persist_assistant_shell,
    persist_user_turn,
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

    The persistence helpers use ``async with shielded_async_session() as
    ws`` and call ``ws.commit()`` internally. Inside the conftest's
    ``join_transaction_mode="create_savepoint"`` setup, those commits
    release a SAVEPOINT instead of committing the outer transaction —
    so the test session can see helper-staged rows immediately and the
    outer rollback at end of test wipes them.
    """

    @asynccontextmanager
    async def _fake_shielded_session():
        yield db_session
        # Do NOT close — the outer fixture owns the session lifecycle.

    monkeypatch.setattr(
        persistence_module,
        "shielded_async_session",
        _fake_shielded_session,
    )
    return db_session


def _accumulator_with_one_call() -> TurnTokenAccumulator:
    acc = TurnTokenAccumulator()
    acc.add(
        model="gpt-4o-mini",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        cost_micros=12345,
    )
    return acc


async def _count_assistant_rows(
    session: AsyncSession, thread_id: int, turn_id: str
) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(NewChatMessage)
        .where(
            NewChatMessage.thread_id == thread_id,
            NewChatMessage.turn_id == turn_id,
            NewChatMessage.role == NewChatMessageRole.ASSISTANT,
        )
    )
    return int(result.scalar_one())


async def _count_token_usage_rows(session: AsyncSession, message_id: int) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(TokenUsage)
        .where(TokenUsage.message_id == message_id)
    )
    return int(result.scalar_one())


# ---------------------------------------------------------------------------
# persist_assistant_shell
# ---------------------------------------------------------------------------


class TestPersistAssistantShell:
    async def test_first_call_inserts_empty_shell_and_returns_id(
        self,
        db_session,
        db_user,
        db_thread,
        patched_shielded_session,
    ):
        # Capture primitive ids before any persistence helper runs:
        # the helpers commit/rollback the shared test session, which
        # can detach ORM rows mid-test.
        thread_id = db_thread.id
        user_id_str = str(db_user.id)
        turn_id = f"{thread_id}:1000"

        msg_id = await persist_assistant_shell(
            chat_id=thread_id,
            user_id=user_id_str,
            turn_id=turn_id,
        )
        assert msg_id is not None and isinstance(msg_id, int)

        row = await db_session.get(NewChatMessage, msg_id)
        assert row is not None
        assert row.thread_id == thread_id
        assert row.role == NewChatMessageRole.ASSISTANT
        assert row.turn_id == turn_id
        # Empty shell payload — finalize_assistant_turn overwrites later.
        assert row.content == [{"type": "text", "text": ""}]

    async def test_second_call_with_same_turn_id_returns_same_id(
        self,
        db_session,
        db_user,
        db_thread,
        patched_shielded_session,
    ):
        # Capture primitive ids before any persistence helper runs:
        # the helpers commit/rollback the shared test session, which
        # can detach ORM rows mid-test.
        thread_id = db_thread.id
        user_id_str = str(db_user.id)
        turn_id = f"{thread_id}:2000"

        first_id = await persist_assistant_shell(
            chat_id=thread_id,
            user_id=user_id_str,
            turn_id=turn_id,
        )
        second_id = await persist_assistant_shell(
            chat_id=thread_id,
            user_id=user_id_str,
            turn_id=turn_id,
        )

        assert first_id is not None
        assert first_id == second_id
        # Exactly one row in the DB for this turn.
        assert await _count_assistant_rows(db_session, thread_id, turn_id) == 1

    async def test_missing_turn_id_returns_none(
        self,
        db_user,
        db_thread,
        patched_shielded_session,
    ):
        thread_id = db_thread.id
        user_id_str = str(db_user.id)

        msg_id = await persist_assistant_shell(
            chat_id=thread_id,
            user_id=user_id_str,
            turn_id="",
        )
        assert msg_id is None

    async def test_after_persist_user_turn_resolves_assistant_id(
        self,
        db_session,
        db_user,
        db_thread,
        patched_shielded_session,
    ):
        thread_id = db_thread.id
        user_id_str = str(db_user.id)
        turn_id = f"{thread_id}:3000"

        # The streaming layer always calls persist_user_turn first, so
        # smoke-test the canonical sequence.
        user_msg_id = await persist_user_turn(
            chat_id=thread_id,
            user_id=user_id_str,
            turn_id=turn_id,
            user_query="hello",
        )
        assert isinstance(user_msg_id, int)

        msg_id = await persist_assistant_shell(
            chat_id=thread_id,
            user_id=user_id_str,
            turn_id=turn_id,
        )
        assert msg_id is not None
        # User row + assistant shell row = 2 rows for this turn.
        result = await db_session.execute(
            select(func.count())
            .select_from(NewChatMessage)
            .where(
                NewChatMessage.thread_id == thread_id,
                NewChatMessage.turn_id == turn_id,
            )
        )
        assert result.scalar_one() == 2

    async def test_double_call_with_same_turn_id_uses_on_conflict(
        self,
        db_session,
        db_user,
        db_thread,
        patched_shielded_session,
    ):
        """Verifies the ON CONFLICT DO NOTHING path on the assistant
        shell does not raise ``IntegrityError`` even when the second
        writer races the first within a tight loop. ``test_second_call_with_same_turn_id_returns_same_id``
        already covers the same-id semantics; this test additionally
        asserts neither call raises so the debugger's
        ``raise-on-IntegrityError`` setting won't pause the streaming
        path under contention.
        """
        thread_id = db_thread.id
        user_id_str = str(db_user.id)
        turn_id = f"{thread_id}:3500"

        # Both calls go through ``pg_insert(...).on_conflict_do_nothing``;
        # the second one returns RETURNING=∅ and falls into the SELECT
        # branch. Neither path raises.
        first_id = await persist_assistant_shell(
            chat_id=thread_id, user_id=user_id_str, turn_id=turn_id
        )
        second_id = await persist_assistant_shell(
            chat_id=thread_id, user_id=user_id_str, turn_id=turn_id
        )
        assert first_id is not None
        assert first_id == second_id


# ---------------------------------------------------------------------------
# persist_user_turn
# ---------------------------------------------------------------------------


class TestPersistUserTurn:
    async def test_returns_message_id_on_first_insert(
        self,
        db_session,
        db_user,
        db_thread,
        patched_shielded_session,
    ):
        thread_id = db_thread.id
        user_id_str = str(db_user.id)
        turn_id = f"{thread_id}:8000"

        msg_id = await persist_user_turn(
            chat_id=thread_id,
            user_id=user_id_str,
            turn_id=turn_id,
            user_query="hello",
        )
        assert isinstance(msg_id, int) and msg_id > 0

        row = await db_session.get(NewChatMessage, msg_id)
        assert row is not None
        assert row.thread_id == thread_id
        assert row.role == NewChatMessageRole.USER
        assert row.turn_id == turn_id
        assert row.content == [{"type": "text", "text": "hello"}]

    async def test_returns_existing_id_on_conflict(
        self,
        db_session,
        db_user,
        db_thread,
        patched_shielded_session,
    ):
        thread_id = db_thread.id
        user_id_str = str(db_user.id)
        turn_id = f"{thread_id}:8100"

        first_id = await persist_user_turn(
            chat_id=thread_id,
            user_id=user_id_str,
            turn_id=turn_id,
            user_query="hello",
        )
        # Second call simulates a legacy FE ``appendMessage`` racing the
        # SSE stream: ON CONFLICT DO NOTHING short-circuits at the DB
        # level, the helper recovers the existing id via SELECT, and
        # crucially does NOT raise ``IntegrityError`` (the debugger
        # would otherwise pause on it).
        second_id = await persist_user_turn(
            chat_id=thread_id,
            user_id=user_id_str,
            turn_id=turn_id,
            user_query="ignored on conflict",
        )
        assert first_id is not None
        assert first_id == second_id

        # Exactly one user row for this turn.
        count = await db_session.execute(
            select(func.count())
            .select_from(NewChatMessage)
            .where(
                NewChatMessage.thread_id == thread_id,
                NewChatMessage.turn_id == turn_id,
                NewChatMessage.role == NewChatMessageRole.USER,
            )
        )
        assert count.scalar_one() == 1

    async def test_embeds_mentioned_documents_part(
        self,
        db_session,
        db_user,
        db_thread,
        patched_shielded_session,
    ):
        """The full ``{id, title, document_type}`` triple forwarded by
        the FE must round-trip into a single ``mentioned-documents``
        ContentPart on the persisted user message — the history loader
        renders the chips on reload from this part directly.
        """
        thread_id = db_thread.id
        user_id_str = str(db_user.id)
        turn_id = f"{thread_id}:8200"

        mentioned = [
            {"id": 11, "title": "Alpha", "document_type": "GENERAL"},
            {"id": 22, "title": "Beta", "document_type": "GENERAL"},
        ]
        msg_id = await persist_user_turn(
            chat_id=thread_id,
            user_id=user_id_str,
            turn_id=turn_id,
            user_query="hello",
            mentioned_documents=mentioned,
        )
        assert isinstance(msg_id, int)

        row = await db_session.get(NewChatMessage, msg_id)
        assert row is not None
        # Content is a 2-part list: text + mentioned-documents.
        assert isinstance(row.content, list)
        assert row.content[0] == {"type": "text", "text": "hello"}
        assert row.content[1] == {
            "type": "mentioned-documents",
            "documents": [
                {"id": 11, "title": "Alpha", "document_type": "GENERAL"},
                {"id": 22, "title": "Beta", "document_type": "GENERAL"},
            ],
        }

    async def test_skips_mentioned_documents_when_empty_or_invalid(
        self,
        db_session,
        db_user,
        db_thread,
        patched_shielded_session,
    ):
        """Empty list and entries missing required fields are dropped;
        a ``mentioned-documents`` part is only emitted when at least
        one normalised entry survived.
        """
        thread_id = db_thread.id
        user_id_str = str(db_user.id)
        turn_id_empty = f"{thread_id}:8300"
        turn_id_invalid = f"{thread_id}:8301"

        msg_id_empty = await persist_user_turn(
            chat_id=thread_id,
            user_id=user_id_str,
            turn_id=turn_id_empty,
            user_query="hi",
            mentioned_documents=[],
        )
        assert isinstance(msg_id_empty, int)
        row_empty = await db_session.get(NewChatMessage, msg_id_empty)
        assert row_empty is not None
        assert row_empty.content == [{"type": "text", "text": "hi"}]

        # Each entry missing one required field — all skipped.
        msg_id_invalid = await persist_user_turn(
            chat_id=thread_id,
            user_id=user_id_str,
            turn_id=turn_id_invalid,
            user_query="hi",
            mentioned_documents=[
                {"title": "no id", "document_type": "GENERAL"},  # missing id
                {"id": 99, "document_type": "GENERAL"},  # missing title
                {"id": 100, "title": "no type"},  # missing document_type
            ],
        )
        assert isinstance(msg_id_invalid, int)
        row_invalid = await db_session.get(NewChatMessage, msg_id_invalid)
        assert row_invalid is not None
        assert row_invalid.content == [{"type": "text", "text": "hi"}]

    async def test_missing_turn_id_returns_none(
        self,
        db_user,
        db_thread,
        patched_shielded_session,
    ):
        thread_id = db_thread.id
        user_id_str = str(db_user.id)

        msg_id = await persist_user_turn(
            chat_id=thread_id,
            user_id=user_id_str,
            turn_id="",
            user_query="hello",
        )
        assert msg_id is None


# ---------------------------------------------------------------------------
# finalize_assistant_turn
# ---------------------------------------------------------------------------


class TestFinalizeAssistantTurn:
    async def test_writes_content_and_token_usage(
        self,
        db_session,
        db_user,
        db_thread,
        db_search_space,
        patched_shielded_session,
    ):
        thread_id = db_thread.id
        user_id_uuid = db_user.id
        user_id_str = str(user_id_uuid)
        search_space_id = db_search_space.id
        turn_id = f"{thread_id}:4000"

        msg_id = await persist_assistant_shell(
            chat_id=thread_id,
            user_id=user_id_str,
            turn_id=turn_id,
        )
        assert msg_id is not None

        rich_content = [
            {"type": "text", "text": "Hello world"},
            {
                "type": "tool-call",
                "toolCallId": "call_x",
                "toolName": "ls",
                "args": {"path": "/"},
                "argsText": '{\n  "path": "/"\n}',
                "result": {"files": []},
                "langchainToolCallId": "lc_x",
            },
        ]
        await finalize_assistant_turn(
            message_id=msg_id,
            chat_id=thread_id,
            search_space_id=search_space_id,
            user_id=user_id_str,
            turn_id=turn_id,
            content=rich_content,
            accumulator=_accumulator_with_one_call(),
        )

        row = await db_session.get(NewChatMessage, msg_id)
        await db_session.refresh(row)
        assert row.content == rich_content

        # Exactly one token_usage row keyed on this message_id.
        usage_rows = (
            (
                await db_session.execute(
                    select(TokenUsage).where(TokenUsage.message_id == msg_id)
                )
            )
            .scalars()
            .all()
        )
        assert len(usage_rows) == 1
        usage = usage_rows[0]
        assert usage.usage_type == "chat"
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 150
        assert usage.cost_micros == 12345
        assert usage.thread_id == thread_id
        assert usage.search_space_id == search_space_id

    async def test_empty_content_writes_status_marker(
        self,
        db_session,
        db_user,
        db_thread,
        db_search_space,
        patched_shielded_session,
    ):
        thread_id = db_thread.id
        user_id_str = str(db_user.id)
        search_space_id = db_search_space.id
        turn_id = f"{thread_id}:5000"

        msg_id = await persist_assistant_shell(
            chat_id=thread_id,
            user_id=user_id_str,
            turn_id=turn_id,
        )
        assert msg_id is not None

        # Pure tool-call turn that aborted before any output, or
        # interrupt before any event arrived — empty list.
        await finalize_assistant_turn(
            message_id=msg_id,
            chat_id=thread_id,
            search_space_id=search_space_id,
            user_id=user_id_str,
            turn_id=turn_id,
            content=[],
            accumulator=None,
        )

        row = await db_session.get(NewChatMessage, msg_id)
        await db_session.refresh(row)
        assert row.content == [{"type": "status", "text": "(no text response)"}]

    async def test_double_call_safe_via_on_conflict(
        self,
        db_session,
        db_user,
        db_thread,
        db_search_space,
        patched_shielded_session,
    ):
        thread_id = db_thread.id
        user_id_str = str(db_user.id)
        search_space_id = db_search_space.id
        turn_id = f"{thread_id}:6000"

        msg_id = await persist_assistant_shell(
            chat_id=thread_id,
            user_id=user_id_str,
            turn_id=turn_id,
        )
        assert msg_id is not None

        first_acc = _accumulator_with_one_call()
        await finalize_assistant_turn(
            message_id=msg_id,
            chat_id=thread_id,
            search_space_id=search_space_id,
            user_id=user_id_str,
            turn_id=turn_id,
            content=[{"type": "text", "text": "first finalize"}],
            accumulator=first_acc,
        )

        # Simulate a follow-up finalize (e.g., resume retry within the
        # shielded finally block firing twice). Different content, but
        # ON CONFLICT DO NOTHING on token_usage means the cost from the
        # first finalize stays authoritative.
        second_acc = TurnTokenAccumulator()
        second_acc.add(
            model="gpt-4o-mini",
            prompt_tokens=999,
            completion_tokens=999,
            total_tokens=1998,
            cost_micros=99999,
        )
        await finalize_assistant_turn(
            message_id=msg_id,
            chat_id=thread_id,
            search_space_id=search_space_id,
            user_id=user_id_str,
            turn_id=turn_id,
            content=[{"type": "text", "text": "second finalize"}],
            accumulator=second_acc,
        )

        # Content was overwritten by the second UPDATE.
        row = await db_session.get(NewChatMessage, msg_id)
        await db_session.refresh(row)
        assert row.content == [{"type": "text", "text": "second finalize"}]

        # But token_usage stayed at exactly one row, preserving the
        # first finalize's authoritative cost.
        assert await _count_token_usage_rows(db_session, msg_id) == 1
        usage = (
            await db_session.execute(
                select(TokenUsage).where(TokenUsage.message_id == msg_id)
            )
        ).scalar_one()
        assert usage.cost_micros == 12345  # First finalize's value

    async def test_append_message_style_insert_after_finalize_no_dupe(
        self,
        db_session,
        db_user,
        db_thread,
        db_search_space,
        patched_shielded_session,
    ):
        """Cross-writer race: ``append_message`` arrives after ``finalize_assistant_turn``.

        Both target the same ``message_id``; the partial unique index
        ``uq_token_usage_message_id`` (migration 142) makes the second
        insert a no-op via ``ON CONFLICT DO NOTHING``.
        """
        from sqlalchemy import text as sa_text

        thread_id = db_thread.id
        user_uuid = db_user.id
        user_id_str = str(user_uuid)
        search_space_id = db_search_space.id
        turn_id = f"{thread_id}:7000"

        msg_id = await persist_assistant_shell(
            chat_id=thread_id,
            user_id=user_id_str,
            turn_id=turn_id,
        )
        assert msg_id is not None

        await finalize_assistant_turn(
            message_id=msg_id,
            chat_id=thread_id,
            search_space_id=search_space_id,
            user_id=user_id_str,
            turn_id=turn_id,
            content=[{"type": "text", "text": "from server"}],
            accumulator=_accumulator_with_one_call(),
        )

        # Now simulate the FE's append_message branch firing AFTER —
        # the same INSERT ... ON CONFLICT DO NOTHING shape used by the
        # route handler, keyed on the migration-142 partial unique
        # index.
        late_insert = (
            pg_insert(TokenUsage)
            .values(
                usage_type="chat",
                prompt_tokens=42,
                completion_tokens=42,
                total_tokens=84,
                cost_micros=1,
                model_breakdown=None,
                call_details=None,
                thread_id=thread_id,
                message_id=msg_id,
                search_space_id=search_space_id,
                user_id=user_uuid,
            )
            .on_conflict_do_nothing(
                index_elements=["message_id"],
                index_where=sa_text("message_id IS NOT NULL"),
            )
        )
        await db_session.execute(late_insert)
        await db_session.flush()

        # Still exactly one row, with the original (server) cost value.
        assert await _count_token_usage_rows(db_session, msg_id) == 1
        usage = (
            await db_session.execute(
                select(TokenUsage).where(TokenUsage.message_id == msg_id)
            )
        ).scalar_one()
        assert usage.cost_micros == 12345

    async def test_helper_never_raises_on_missing_message_id(
        self,
        db_session,
        db_user,
        db_thread,
        db_search_space,
        patched_shielded_session,
    ):
        thread_id = db_thread.id
        user_id_str = str(db_user.id)
        search_space_id = db_search_space.id

        # message_id that doesn't exist — finalize must log+return,
        # never raise (called from shielded finally).
        await finalize_assistant_turn(
            message_id=999_999_999,
            chat_id=thread_id,
            search_space_id=search_space_id,
            user_id=user_id_str,
            turn_id="anything",
            content=[{"type": "text", "text": "x"}],
            accumulator=_accumulator_with_one_call(),
        )
        # If we got here without an exception, the test passes.
        # Sanity: no token_usage row created (FK to message would have
        # been rejected anyway, but ON CONFLICT path may swallow
        # FK errors as well; check directly).
        assert await _count_token_usage_rows(db_session, 999_999_999) == 0
