"""Unit tests for the filesystem-tool branches of ``revert_service``.

Covers:

* Exact-name dispatch — ``rmdir`` does NOT mis-route to the document
  branch (``"rmdir".startswith("rm")`` would mis-route under the legacy
  prefix-based dispatch).
* ``rm`` revert re-INSERTs a fresh document from the snapshot, including
  re-creating chunks. Falls back to ``(folder_id_before, title_before)``
  when ``metadata_before["virtual_path"]`` is missing.
* ``write_file`` create-revert (``content_before IS NULL``) DELETEs the
  document.
* ``rmdir`` revert re-INSERTs a fresh folder from the snapshot.
* ``mkdir`` revert DELETEs the empty folder; reports ``tool_unavailable``
  when the folder gained children.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from app.services import revert_service

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _stub_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        revert_service,
        "embed_texts",
        lambda texts: [np.zeros(8, dtype=np.float32) for _ in texts],
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeResult:
    def __init__(self, rows: list[Any] | None = None, scalar: Any = None) -> None:
        self._rows = rows or []
        self._scalar = scalar

    def all(self) -> list[Any]:
        return list(self._rows)

    def scalar_one_or_none(self) -> Any:
        return self._scalar

    def scalars(self) -> Any:
        return _FakeScalarsProxy(self._rows)


class _FakeScalarsProxy:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def first(self) -> Any:
        return self._rows[0] if self._rows else None


class _FakeSession:
    def __init__(self) -> None:
        self.execute = AsyncMock()
        self.added: list[Any] = []
        self.deleted: list[Any] = []
        self.flush = AsyncMock()
        # session.get(Model, pk) lookup
        self.get = AsyncMock(return_value=None)

        async def _flush_assigning_ids() -> None:
            for obj in self.added:
                if getattr(obj, "id", None) is None:
                    obj.id = 999

        self.flush.side_effect = _flush_assigning_ids

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    def add_all(self, objs: list[Any]) -> None:
        self.added.extend(objs)


def _action(*, tool_name: str, action_id: int = 7):
    return MagicMock(
        id=action_id,
        tool_name=tool_name,
        thread_id=1,
        search_space_id=2,
        user_id="user-1",
        reverse_descriptor=None,
    )


def _doc_revision(
    *,
    document_id: int | None = None,
    content_before: str | None = "old content",
    title_before: str | None = "notes.md",
    folder_id_before: int | None = 5,
    chunks_before: list[dict[str, str]] | None = None,
    metadata_before: dict[str, str] | None = None,
):
    revision = MagicMock()
    revision.id = 100
    revision.document_id = document_id
    revision.search_space_id = 2
    revision.content_before = content_before
    revision.title_before = title_before
    revision.folder_id_before = folder_id_before
    revision.chunks_before = chunks_before or []
    revision.metadata_before = metadata_before
    return revision


def _folder_revision(
    *,
    folder_id: int | None = None,
    name_before: str | None = "team",
    parent_id_before: int | None = None,
    position_before: str | None = "a0",
):
    revision = MagicMock()
    revision.id = 200
    revision.folder_id = folder_id
    revision.search_space_id = 2
    revision.name_before = name_before
    revision.parent_id_before = parent_id_before
    revision.position_before = position_before
    return revision


# ---------------------------------------------------------------------------
# Exact-name dispatch regression guards
# ---------------------------------------------------------------------------


class TestExactDispatch:
    """Regression: ``rmdir`` MUST NOT route to the document branch."""

    @pytest.mark.asyncio
    async def test_rmdir_does_not_misroute_to_document(self) -> None:
        # If dispatch used `startswith("rm")` we'd hit the document branch
        # here. With exact-name lookup `rmdir` lands in `_FOLDER_TOOLS`.
        session = _FakeSession()
        action = _action(tool_name="rmdir")
        # No folder revisions exist for this action.
        session.execute.return_value = _FakeResult(rows=[])
        outcome = await revert_service.revert_action(
            session,  # type: ignore[arg-type]
            action=action,
            requester_user_id="user-1",
        )
        assert outcome.status == "not_reversible"
        assert "folder_revisions" in outcome.message

    def test_dispatch_sets_split_doc_and_folder(self) -> None:
        # Static guards on the dispatch tables themselves so a future
        # refactor doesn't accidentally reintroduce the prefix bug.
        assert "rm" in revert_service._DOC_TOOLS
        assert "rmdir" in revert_service._FOLDER_TOOLS
        assert "rmdir" not in revert_service._DOC_TOOLS
        assert "rm" not in revert_service._FOLDER_TOOLS
        # ``move_file`` lives only in document tools (it's a doc rename).
        assert "move_file" in revert_service._DOC_TOOLS
        assert "move_file" not in revert_service._FOLDER_TOOLS


# ---------------------------------------------------------------------------
# rm revert (re-INSERT)
# ---------------------------------------------------------------------------


class TestRmRevert:
    @pytest.mark.asyncio
    async def test_re_inserts_document_with_chunks(self) -> None:
        session = _FakeSession()
        revision = _doc_revision(
            document_id=None,  # row was hard-deleted
            content_before="hello world",
            title_before="x.md",
            folder_id_before=None,
            chunks_before=[{"content": "alpha"}, {"content": "beta"}],
            metadata_before={"virtual_path": "/documents/x.md"},
        )
        # No collision check hit and the resulting query returns nothing.
        session.execute.return_value = _FakeResult(scalar=None)

        outcome = await revert_service._reinsert_document_from_revision(
            session,  # type: ignore[arg-type]
            revision=revision,
        )

        assert outcome.status == "ok"
        # New Document + 2 chunks must have been added.
        from app.db import Chunk, Document

        added_docs = [obj for obj in session.added if isinstance(obj, Document)]
        added_chunks = [obj for obj in session.added if isinstance(obj, Chunk)]
        assert len(added_docs) == 1
        assert added_docs[0].title == "x.md"
        assert len(added_chunks) == 2
        # Snapshot was repointed at the new doc id so a follow-up revert works.
        assert revision.document_id == added_docs[0].id

    @pytest.mark.asyncio
    async def test_falls_back_to_folder_id_and_title_for_virtual_path(
        self,
    ) -> None:
        session = _FakeSession()
        # Snapshot with NO metadata_before — the fallback path must kick in.
        revision = _doc_revision(
            document_id=None,
            content_before="hello",
            title_before="cap.md",
            folder_id_before=42,
            chunks_before=[],
            metadata_before=None,
        )
        # session.get(Folder, 42) returns a folder with a name.
        folder = MagicMock()
        folder.name = "team"
        folder.parent_id = None
        # First .get is for the folder lookup in the path-derivation.
        session.get = AsyncMock(return_value=folder)
        session.execute.return_value = _FakeResult(scalar=None)

        outcome = await revert_service._reinsert_document_from_revision(
            session,  # type: ignore[arg-type]
            revision=revision,
        )
        assert outcome.status == "ok"

    @pytest.mark.asyncio
    async def test_falls_back_to_root_path_when_no_folder(
        self,
    ) -> None:
        """metadata_before is None and folder_id_before is None still
        resolves: title fallback yields ``/documents/<title>`` so revert
        proceeds at the root of the documents tree."""
        session = _FakeSession()
        revision = _doc_revision(
            document_id=None,
            content_before="hello",
            title_before="x.md",
            folder_id_before=None,
            metadata_before=None,
        )
        # No collision in the documents tree at /documents/x.md.
        session.execute.return_value = _FakeResult(scalar=None)
        outcome = await revert_service._reinsert_document_from_revision(
            session,  # type: ignore[arg-type]
            revision=revision,
        )
        assert outcome.status == "ok"

    @pytest.mark.asyncio
    async def test_collision_with_live_doc_returns_tool_unavailable(self) -> None:
        session = _FakeSession()
        revision = _doc_revision(
            document_id=None,
            content_before="hi",
            title_before="x.md",
            folder_id_before=None,
            metadata_before={"virtual_path": "/documents/x.md"},
        )
        # SELECT for unique_identifier_hash collision hits an existing row.
        session.execute.return_value = _FakeResult(scalar=42)
        outcome = await revert_service._reinsert_document_from_revision(
            session,  # type: ignore[arg-type]
            revision=revision,
        )
        assert outcome.status == "tool_unavailable"
        assert "collide" in outcome.message


# ---------------------------------------------------------------------------
# write_file create revert (DELETE)
# ---------------------------------------------------------------------------


class TestWriteFileCreateRevert:
    @pytest.mark.asyncio
    async def test_deletes_created_doc(self) -> None:
        session = _FakeSession()
        revision = _doc_revision(
            document_id=99,
            content_before=None,  # marker for "created in this action"
            title_before=None,
        )
        outcome = await revert_service._delete_created_document(
            session,  # type: ignore[arg-type]
            revision=revision,
        )
        assert outcome.status == "ok"
        # Exactly one DELETE was issued.
        assert session.execute.await_count == 1


# ---------------------------------------------------------------------------
# rmdir revert (re-INSERT folder)
# ---------------------------------------------------------------------------


class TestRmdirRevert:
    @pytest.mark.asyncio
    async def test_re_inserts_folder_from_snapshot(self) -> None:
        session = _FakeSession()
        revision = _folder_revision(
            folder_id=None,
            name_before="team",
            parent_id_before=None,
            position_before="a0",
        )
        outcome = await revert_service._reinsert_folder_from_revision(
            session,  # type: ignore[arg-type]
            revision=revision,
        )
        from app.db import Folder

        assert outcome.status == "ok"
        added_folders = [obj for obj in session.added if isinstance(obj, Folder)]
        assert len(added_folders) == 1
        assert added_folders[0].name == "team"
        assert revision.folder_id == added_folders[0].id


# ---------------------------------------------------------------------------
# mkdir revert (DELETE folder)
# ---------------------------------------------------------------------------


class TestMkdirRevert:
    @pytest.mark.asyncio
    async def test_deletes_empty_folder(self) -> None:
        session = _FakeSession()
        revision = _folder_revision(folder_id=42)
        # Both the doc-existence check and the child-folder check return None.
        session.execute.side_effect = [
            _FakeResult(scalar=None),  # docs
            _FakeResult(scalar=None),  # children
            _FakeResult(scalar=None),  # delete (no return value)
        ]
        outcome = await revert_service._delete_created_folder(
            session,  # type: ignore[arg-type]
            revision=revision,
        )
        assert outcome.status == "ok"
        # 3 executes: docs check, children check, delete.
        assert session.execute.await_count == 3

    @pytest.mark.asyncio
    async def test_reports_tool_unavailable_when_folder_has_children(self) -> None:
        session = _FakeSession()
        revision = _folder_revision(folder_id=42)
        # First check (docs) returns "row found".
        session.execute.return_value = _FakeResult(scalar=1)
        outcome = await revert_service._delete_created_folder(
            session,  # type: ignore[arg-type]
            revision=revision,
        )
        assert outcome.status == "tool_unavailable"
        assert "no longer empty" in outcome.message
