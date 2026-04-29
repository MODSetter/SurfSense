"""Unit tests for kb_persistence filesystem-parity invariants.

Specifically, these tests pin down that the agent-driven write_file flow
treats path uniqueness — not content uniqueness — as the only hard
invariant. This mirrors a real filesystem: ``cp a b`` produces two files
with identical bytes living at different paths, and that should round-trip
through :class:`KnowledgeBasePersistenceMiddleware` without losing the copy.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from app.agents.new_chat.middleware import kb_persistence
from app.db import Document


class _FakeResult:
    """Minimal stand-in for ``sqlalchemy.engine.Result``."""

    def __init__(self, value: Any = None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalar(self) -> Any:
        return self._value


class _FakeSession:
    """Minimal AsyncSession stand-in scoped to ``_create_document`` needs.

    Records every ``add`` so we can assert against the resulting Documents
    and Chunks. ``execute`` always returns "no row" by default — i.e. no
    folder hierarchy preexists and no path collision exists. Tests that
    want a path collision can override that on a per-call basis.
    """

    def __init__(self) -> None:
        self.added: list[Any] = []
        self.execute = AsyncMock(return_value=_FakeResult(None))
        self.flush = AsyncMock()

        # Simulate ``await session.flush()`` assigning an id to the doc;
        # we increment a counter so each Document gets a unique id.
        self._next_id = 1

        async def _flush_assigning_ids() -> None:
            for obj in self.added:
                if getattr(obj, "id", None) is None:
                    obj.id = self._next_id
                    self._next_id += 1

        self.flush.side_effect = _flush_assigning_ids

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    def add_all(self, objs: list[Any]) -> None:
        self.added.extend(objs)


@pytest.fixture(autouse=True)
def _stub_embeddings_and_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avoid loading the embedding model in unit tests."""
    monkeypatch.setattr(
        kb_persistence,
        "embed_texts",
        lambda texts: [np.zeros(8, dtype=np.float32) for _ in texts],
    )
    monkeypatch.setattr(kb_persistence, "chunk_text", lambda content: [content])


@pytest.mark.asyncio
async def test_create_document_allows_identical_content_at_different_paths() -> None:
    """The core regression: ``cp /a/notes.md /b/notes-copy.md``.

    Both create calls must succeed even though the bytes are byte-for-byte
    identical, because path is the only filesystem-style unique key.
    """
    session = _FakeSession()
    content = "# Same body\n\nIdentical content used by two different paths.\n"

    first = await kb_persistence._create_document(
        session,  # type: ignore[arg-type]
        virtual_path="/documents/a/notes.md",
        content=content,
        search_space_id=42,
        created_by_id="user-1",
    )
    assert isinstance(first, Document)
    assert first.title == "notes.md"

    # Second create with byte-identical content at a different path should
    # not raise — that's the whole point of the filesystem-parity fix.
    second = await kb_persistence._create_document(
        session,  # type: ignore[arg-type]
        virtual_path="/documents/b/notes-copy.md",
        content=content,
        search_space_id=42,
        created_by_id="user-1",
    )
    assert isinstance(second, Document)
    assert second.title == "notes-copy.md"

    # Both rows share the same content_hash but live at distinct paths
    # (distinct ``unique_identifier_hash``). That's the desired contract.
    assert first.content_hash == second.content_hash
    assert first.unique_identifier_hash != second.unique_identifier_hash


@pytest.mark.asyncio
async def test_create_document_still_rejects_path_collision() -> None:
    """Path uniqueness remains the hard invariant.

    If ``unique_identifier_hash`` already points at an existing row in
    the same search space, the create call must raise ``ValueError``
    with a clear message — matching the behavior the commit loop relies
    on to upsert via the existing-row code path.
    """
    session = _FakeSession()

    # Path with no folder parts so ``_ensure_folder_hierarchy`` is a
    # no-op and the only SELECT executed is the path-collision check.
    # That SELECT returns an existing doc id, triggering the guard.
    session.execute = AsyncMock(return_value=_FakeResult(value=99))

    with pytest.raises(ValueError, match="already exists at path"):
        await kb_persistence._create_document(
            session,  # type: ignore[arg-type]
            virtual_path="/documents/notes.md",
            content="anything",
            search_space_id=42,
            created_by_id="user-1",
        )


@pytest.mark.asyncio
async def test_create_document_does_not_query_for_content_hash_collision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression guard: the legacy second SELECT (content_hash collision
    pre-check) must be gone. Counting ``execute`` calls is a brittle but
    effective way to lock that in.

    The current flow runs exactly one ``execute`` for the path-collision
    SELECT (no folder parts in this path → ``_ensure_folder_hierarchy``
    short-circuits). If a future refactor reintroduces a content-hash
    SELECT, this test will fail loud.
    """
    session = _FakeSession()
    await kb_persistence._create_document(
        session,  # type: ignore[arg-type]
        virtual_path="/documents/notes.md",
        content="hello",
        search_space_id=42,
        created_by_id="user-1",
    )
    # Path-collision SELECT only. No content_hash SELECT.
    assert session.execute.await_count == 1, (
        f"Unexpected execute count {session.execute.await_count}; "
        "did the legacy content_hash collision pre-check get re-added?"
    )
