"""Unit tests for the kb_persistence snapshot helpers.

The full ``commit_staged_filesystem_state`` body exercises a real session
in integration tests; here we verify the building blocks used by the
snapshot/revert pipeline:

* ``_find_action_ids_batch`` issues a SINGLE query for N tool_call_ids
  (regression guard against the N+1 lookup pattern).
* ``_mark_action_reversible`` is a no-op when ``action_id`` is ``None``.
* ``_doc_revision_payload`` and ``_load_chunks_for_snapshot`` produce the
  shape the snapshot helpers consume.

These tests use ``MagicMock`` / ``AsyncMock`` against a fake session so
the assertions run in milliseconds and don't require Postgres.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.new_chat.middleware import kb_persistence

pytestmark = pytest.mark.unit


class _FakeResult:
    def __init__(self, rows: list[Any] | None = None, scalar: Any = None) -> None:
        self._rows = rows or []
        self._scalar = scalar

    def all(self) -> list[Any]:
        return list(self._rows)

    def scalar_one_or_none(self) -> Any:
        return self._scalar


class _FakeSession:
    def __init__(self) -> None:
        self.execute = AsyncMock()


@pytest.mark.asyncio
async def test_find_action_ids_batch_issues_single_query() -> None:
    """The lookup MUST be a single ``IN (...)`` SELECT, not N selects."""
    session = _FakeSession()
    session.execute.return_value = _FakeResult(
        rows=[
            MagicMock(id=11, tool_call_id="tc-a"),
            MagicMock(id=22, tool_call_id="tc-b"),
            MagicMock(id=33, tool_call_id="tc-c"),
        ]
    )

    mapping = await kb_persistence._find_action_ids_batch(
        session,  # type: ignore[arg-type]
        thread_id=1,
        tool_call_ids={"tc-a", "tc-b", "tc-c"},
    )

    assert mapping == {"tc-a": 11, "tc-b": 22, "tc-c": 33}
    assert session.execute.await_count == 1, (
        "Snapshot binding must batch into ONE query; got "
        f"{session.execute.await_count} (regression: N+1 lookup pattern)."
    )


@pytest.mark.asyncio
async def test_find_action_ids_batch_short_circuits_when_thread_id_missing() -> None:
    session = _FakeSession()
    mapping = await kb_persistence._find_action_ids_batch(
        session,  # type: ignore[arg-type]
        thread_id=None,
        tool_call_ids={"tc-a"},
    )
    assert mapping == {}
    assert session.execute.await_count == 0


@pytest.mark.asyncio
async def test_find_action_ids_batch_short_circuits_when_no_calls() -> None:
    session = _FakeSession()
    mapping = await kb_persistence._find_action_ids_batch(
        session,  # type: ignore[arg-type]
        thread_id=42,
        tool_call_ids=set(),
    )
    assert mapping == {}
    assert session.execute.await_count == 0


@pytest.mark.asyncio
async def test_mark_action_reversible_is_noop_for_null_id() -> None:
    session = _FakeSession()
    await kb_persistence._mark_action_reversible(session, action_id=None)  # type: ignore[arg-type]
    assert session.execute.await_count == 0


@pytest.mark.asyncio
async def test_mark_action_reversible_runs_update_for_real_id() -> None:
    session = _FakeSession()
    await kb_persistence._mark_action_reversible(session, action_id=99)  # type: ignore[arg-type]
    assert session.execute.await_count == 1


def test_doc_revision_payload_captures_metadata_virtual_path() -> None:
    """Snapshot helpers must capture ``metadata_before`` for revert reuse."""
    doc = MagicMock()
    doc.content = "body"
    doc.title = "notes.md"
    doc.folder_id = 7
    doc.document_metadata = {"virtual_path": "/documents/team/notes.md"}

    payload = kb_persistence._doc_revision_payload(
        doc, chunks_before=[{"content": "x"}]
    )

    assert payload["title_before"] == "notes.md"
    assert payload["folder_id_before"] == 7
    assert payload["content_before"] == "body"
    assert payload["chunks_before"] == [{"content": "x"}]
    assert payload["metadata_before"] == {"virtual_path": "/documents/team/notes.md"}


def test_doc_revision_payload_handles_missing_metadata() -> None:
    doc = MagicMock()
    doc.content = ""
    doc.title = ""
    doc.folder_id = None
    doc.document_metadata = None
    payload = kb_persistence._doc_revision_payload(doc)
    assert payload["metadata_before"] is None


@pytest.mark.asyncio
async def test_load_chunks_for_snapshot_returns_content_only() -> None:
    """Snapshot chunks intentionally omit embeddings (regenerated on revert)."""
    session = _FakeSession()
    session.execute.return_value = _FakeResult(
        rows=[
            MagicMock(content="alpha"),
            MagicMock(content="beta"),
        ]
    )
    chunks = await kb_persistence._load_chunks_for_snapshot(
        session,
        doc_id=42,  # type: ignore[arg-type]
    )
    assert chunks == [{"content": "alpha"}, {"content": "beta"}]


# ---------------------------------------------------------------------------
# Deferred reversibility-flip dispatches.
#
# The snapshot helpers used to dispatch ``action_log_updated`` directly
# from inside the SAVEPOINT block. That meant the SSE side-channel
# could tell the UI a row was reversible while the OUTER transaction
# was still pending — and if the outer commit failed, every SAVEPOINT
# rolled back too, leaving the UI in a state inconsistent with
# durable storage. The deferred-dispatch contract fixes that:
#
#   • when a ``deferred_dispatches`` list is provided, the helper
#     APPENDS the action_id and does NOT dispatch;
#   • the caller (``commit_staged_filesystem_state``) flushes the list
#     only AFTER ``await session.commit()`` succeeds; on rollback it
#     clears the list so nothing is emitted.
# ---------------------------------------------------------------------------


class _NestedCtx:
    """Async context manager mimicking ``session.begin_nested()``."""

    async def __aenter__(self) -> _NestedCtx:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


@pytest.mark.asyncio
async def test_pre_write_snapshot_defers_dispatch_when_list_provided(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Helpers MUST queue dispatches when ``deferred_dispatches`` is set."""
    session = MagicMock()
    session.begin_nested = MagicMock(return_value=_NestedCtx())
    session.execute = AsyncMock(return_value=_FakeResult(rows=[]))
    session.flush = AsyncMock()

    def _add(rev: Any) -> None:
        rev.id = 17

    session.add = MagicMock(side_effect=_add)

    dispatched: list[int] = []

    async def _fake_dispatch(action_id: int | None) -> None:
        if action_id is not None:
            dispatched.append(int(action_id))

    monkeypatch.setattr(
        kb_persistence, "_dispatch_reversibility_update", _fake_dispatch
    )

    deferred: list[int] = []
    doc = MagicMock(id=99, document_metadata={"virtual_path": "/documents/x.md"})
    doc.title = "x.md"
    doc.folder_id = None
    doc.content = "body"

    rev_id = await kb_persistence._snapshot_document_pre_write(
        session,  # type: ignore[arg-type]
        doc=doc,
        action_id=42,
        search_space_id=1,
        turn_id="t-1",
        deferred_dispatches=deferred,
    )

    assert rev_id == 17
    # Inline dispatch must NOT have fired; the action_id is queued.
    assert dispatched == []
    assert deferred == [42]


@pytest.mark.asyncio
async def test_pre_write_snapshot_dispatches_inline_when_list_omitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Direct callers (no outer transaction) keep the legacy inline dispatch."""
    session = MagicMock()
    session.begin_nested = MagicMock(return_value=_NestedCtx())
    session.execute = AsyncMock(return_value=_FakeResult(rows=[]))
    session.flush = AsyncMock()

    def _add(rev: Any) -> None:
        rev.id = 7

    session.add = MagicMock(side_effect=_add)

    dispatched: list[int] = []

    async def _fake_dispatch(action_id: int | None) -> None:
        if action_id is not None:
            dispatched.append(int(action_id))

    monkeypatch.setattr(
        kb_persistence, "_dispatch_reversibility_update", _fake_dispatch
    )

    doc = MagicMock(id=11, document_metadata={"virtual_path": "/documents/y.md"})
    doc.title = "y.md"
    doc.folder_id = None
    doc.content = "body"

    await kb_persistence._snapshot_document_pre_write(
        session,  # type: ignore[arg-type]
        doc=doc,
        action_id=88,
        search_space_id=1,
        turn_id="t-1",
        # No deferred_dispatches arg — fall back to inline dispatch.
    )

    assert dispatched == [88]


@pytest.mark.asyncio
async def test_pre_mkdir_snapshot_defers_dispatch_when_list_provided(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Folder mkdir snapshots honour the same deferred-dispatch contract."""
    session = MagicMock()
    session.begin_nested = MagicMock(return_value=_NestedCtx())
    session.execute = AsyncMock()  # _mark_action_reversible calls execute
    session.flush = AsyncMock()

    def _add(rev: Any) -> None:
        rev.id = 3

    session.add = MagicMock(side_effect=_add)

    dispatched: list[int] = []

    async def _fake_dispatch(action_id: int | None) -> None:
        if action_id is not None:
            dispatched.append(int(action_id))

    monkeypatch.setattr(
        kb_persistence, "_dispatch_reversibility_update", _fake_dispatch
    )

    deferred: list[int] = []
    folder = MagicMock(id=2, name="f", parent_id=None, position="a0")

    await kb_persistence._snapshot_folder_pre_mkdir(
        session,  # type: ignore[arg-type]
        folder=folder,
        action_id=55,
        search_space_id=1,
        turn_id="t-1",
        deferred_dispatches=deferred,
    )

    assert dispatched == []
    assert deferred == [55]
