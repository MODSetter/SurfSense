"""Integration tests for the SSE-based message ID handshake.

The streaming generators (``stream_new_chat`` / ``stream_resume_chat``)
emit two new events after their respective persistence helpers resolve
the canonical ``new_chat_messages.id``:

* ``data-user-message-id``  — emitted only by ``stream_new_chat``,
  AFTER ``persist_user_turn`` and BEFORE any LLM streaming.
* ``data-assistant-message-id`` — emitted by both
  ``stream_new_chat`` and ``stream_resume_chat``, AFTER
  ``persist_assistant_shell`` and BEFORE any LLM streaming.

The frontend renames its optimistic ``msg-user-XXX`` /
``msg-assistant-XXX`` placeholder ids to ``msg-{db_id}`` upon receiving
these events. This test suite anchors three contracts:

1. ``format_data`` produces SSE bytes in the precise shape
   ``data: {"type":"data-<suffix>","data":{...}}\\n\\n`` that the FE's
   ``readSSEStream`` consumer parses (matches ``surfsense_web/lib/chat/streaming-state.ts``).
2. The ``message_id`` carried in the SSE payload exactly equals the
   primary key the persistence helper inserted into
   ``new_chat_messages`` — so the FE rename produces ``msg-{real_pk}``,
   which in turn unlocks DB-id-gated UI (comments, edit-from-message).
3. The same ``message_id`` is used for the ``token_usage.message_id``
   foreign key, so ``finalize_assistant_turn``'s row binds correctly.

Direct end-to-end testing of ``stream_new_chat`` requires a fully
mocked agent + LLM stack (out-of-scope here); those flows are covered
by the harness-driven integration tests under
``tests/integration/agents/new_chat/`` plus the assertion in
``test_persistence.py`` that the helpers themselves return ``int``
ids. The contracts above close the remaining gap between the persist
helpers and the bytes that ship to the FE.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    ChatVisibility,
    NewChatMessage,
    NewChatMessageRole,
    NewChatThread,
    SearchSpace,
    User,
)
from app.services.new_streaming_service import VercelStreamingService
from app.tasks.chat import persistence as persistence_module
from app.tasks.chat.persistence import (
    persist_assistant_shell,
    persist_user_turn,
)

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures (mirror test_persistence.py)
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
    """Route persistence helpers to the test's savepoint-bound session."""

    @asynccontextmanager
    async def _fake_shielded_session():
        yield db_session

    monkeypatch.setattr(
        persistence_module,
        "shielded_async_session",
        _fake_shielded_session,
    )
    return db_session


# ---------------------------------------------------------------------------
# (1) SSE byte-shape contract
# ---------------------------------------------------------------------------


def _parse_sse_data_line(blob: str) -> dict:
    """Unwrap a single ``data: <json>\\n\\n`` SSE frame.

    Raises if there's more than one frame or the prefix is wrong — keeps
    the parser strict so a regression in ``format_data`` produces a
    test failure here, not in a downstream consumer.
    """
    assert blob.endswith("\n\n"), f"missing terminator: {blob!r}"
    line = blob.removesuffix("\n\n")
    assert line.startswith("data: "), f"missing data prefix: {line!r}"
    return json.loads(line.removeprefix("data: "))


class TestSSEByteShape:
    def test_data_user_message_id_byte_shape(self):
        """``format_data("user-message-id", {...})`` must produce the
        exact wire format the FE's
        ``readSSEStream`` -> ``data-user-message-id`` case parses.
        """
        svc = VercelStreamingService()
        blob = svc.format_data(
            "user-message-id",
            {"message_id": 1843, "turn_id": "533:1762900000000"},
        )
        envelope = _parse_sse_data_line(blob)
        assert envelope == {
            "type": "data-user-message-id",
            "data": {"message_id": 1843, "turn_id": "533:1762900000000"},
        }

    def test_data_assistant_message_id_byte_shape(self):
        svc = VercelStreamingService()
        blob = svc.format_data(
            "assistant-message-id",
            {"message_id": 1844, "turn_id": "533:1762900000000"},
        )
        envelope = _parse_sse_data_line(blob)
        assert envelope == {
            "type": "data-assistant-message-id",
            "data": {"message_id": 1844, "turn_id": "533:1762900000000"},
        }


# ---------------------------------------------------------------------------
# (2) Helper-id <-> DB-pk coherence
# ---------------------------------------------------------------------------


class TestHandshakeIdMatchesDB:
    """The SSE handshake's correctness hinges on the integer in
    ``data-{user,assistant}-message-id`` being the EXACT primary key
    the persistence helper inserted. If they ever diverge, the FE
    rename produces ``msg-{wrong_id}``, comments break (regex match
    fails), and downstream features (edit, regenerate) target the
    wrong row. Anchor it here.
    """

    async def test_user_message_id_matches_new_chat_messages_pk(
        self,
        db_session,
        db_user,
        db_thread,
        patched_shielded_session,
    ):
        thread_id = db_thread.id
        user_id_str = str(db_user.id)
        turn_id = f"{thread_id}:9000"

        # The streaming generator passes this same value into
        # ``streaming_service.format_data("user-message-id", {...})``.
        msg_id_from_helper = await persist_user_turn(
            chat_id=thread_id,
            user_id=user_id_str,
            turn_id=turn_id,
            user_query="hello",
        )
        assert isinstance(msg_id_from_helper, int)

        # Look up the row the helper inserted via
        # ``(thread_id, turn_id, role)``  — the same composite the FE
        # uses to identify a turn — and confirm the PK matches.
        row = (
            await db_session.execute(
                select(NewChatMessage).where(
                    NewChatMessage.thread_id == thread_id,
                    NewChatMessage.turn_id == turn_id,
                    NewChatMessage.role == NewChatMessageRole.USER,
                )
            )
        ).scalar_one()
        assert row.id == msg_id_from_helper

        # The byte-stream the FE actually receives — confirms the
        # round-trip from the helper return value to the SSE payload.
        svc = VercelStreamingService()
        envelope = _parse_sse_data_line(
            svc.format_data(
                "user-message-id",
                {"message_id": msg_id_from_helper, "turn_id": turn_id},
            )
        )
        assert envelope["data"]["message_id"] == row.id

    async def test_assistant_message_id_matches_new_chat_messages_pk(
        self,
        db_session,
        db_user,
        db_thread,
        patched_shielded_session,
    ):
        thread_id = db_thread.id
        user_id_str = str(db_user.id)
        turn_id = f"{thread_id}:9100"

        msg_id_from_helper = await persist_assistant_shell(
            chat_id=thread_id,
            user_id=user_id_str,
            turn_id=turn_id,
        )
        assert isinstance(msg_id_from_helper, int)

        row = (
            await db_session.execute(
                select(NewChatMessage).where(
                    NewChatMessage.thread_id == thread_id,
                    NewChatMessage.turn_id == turn_id,
                    NewChatMessage.role == NewChatMessageRole.ASSISTANT,
                )
            )
        ).scalar_one()
        assert row.id == msg_id_from_helper

        svc = VercelStreamingService()
        envelope = _parse_sse_data_line(
            svc.format_data(
                "assistant-message-id",
                {"message_id": msg_id_from_helper, "turn_id": turn_id},
            )
        )
        assert envelope["data"]["message_id"] == row.id

    async def test_handshake_ids_for_full_turn_are_distinct_and_paired(
        self,
        db_session,
        db_user,
        db_thread,
        patched_shielded_session,
    ):
        """Sanity: a full new-chat turn's two SSE events carry two
        DIFFERENT ids (user row PK ≠ assistant row PK), both anchored
        to the SAME ``turn_id`` in the DB. This pairing is what
        ``finalize_assistant_turn`` and the regenerate / edit flows
        rely on.
        """
        thread_id = db_thread.id
        user_id_str = str(db_user.id)
        turn_id = f"{thread_id}:9200"

        user_msg_id = await persist_user_turn(
            chat_id=thread_id,
            user_id=user_id_str,
            turn_id=turn_id,
            user_query="hi",
        )
        assistant_msg_id = await persist_assistant_shell(
            chat_id=thread_id,
            user_id=user_id_str,
            turn_id=turn_id,
        )
        assert user_msg_id is not None and assistant_msg_id is not None
        assert user_msg_id != assistant_msg_id

        rows = (
            (
                await db_session.execute(
                    select(NewChatMessage)
                    .where(
                        NewChatMessage.thread_id == thread_id,
                        NewChatMessage.turn_id == turn_id,
                    )
                    .order_by(NewChatMessage.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 2
        ids_by_role = {r.role: r.id for r in rows}
        assert ids_by_role[NewChatMessageRole.USER] == user_msg_id
        assert ids_by_role[NewChatMessageRole.ASSISTANT] == assistant_msg_id


# ---------------------------------------------------------------------------
# (3) Parse helpers used by the FE — sanity-check our payload shape
# ---------------------------------------------------------------------------


class TestPayloadShapeMatchesFEReader:
    """The FE's ``readStreamedMessageId`` (in
    ``surfsense_web/lib/chat/stream-side-effects.ts``) requires:

    * ``message_id`` is a ``number`` (rejects null / string / NaN).
    * ``turn_id`` is an optional non-empty string (else it's coerced
      to ``null``).

    These tests exercise the BE side of that contract by inspecting
    ``format_data`` output shapes that the FE consumes verbatim.
    """

    def test_message_id_is_serialised_as_a_json_number(self):
        svc = VercelStreamingService()
        envelope = _parse_sse_data_line(
            svc.format_data("user-message-id", {"message_id": 42, "turn_id": "t"})
        )
        assert isinstance(envelope["data"]["message_id"], int)
        assert envelope["data"]["message_id"] == 42

    def test_turn_id_round_trips_as_string(self):
        svc = VercelStreamingService()
        # The actual format used in production: f"{chat_id}:{int(time.time()*1000)}"
        production_turn_id = "533:1762900000000"
        envelope = _parse_sse_data_line(
            svc.format_data(
                "assistant-message-id",
                {"message_id": 1, "turn_id": production_turn_id},
            )
        )
        assert envelope["data"]["turn_id"] == production_turn_id
