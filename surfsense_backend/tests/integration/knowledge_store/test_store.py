"""KnowledgeStore facade end to end: real git engine + real Redis write lock."""

from __future__ import annotations

import pytest

from app.knowledge_store import KnowledgeStore
from app.knowledge_store.engines.git import GitContentEngine
from app.knowledge_store.locks import (
    KnowledgeStoreLockError,
    workspace_write_lock,
)

pytestmark = pytest.mark.integration

AUTHOR = "SurfSense <1@users.surfsense>"


@pytest.fixture
def store(tmp_path, workspace_id) -> KnowledgeStore:
    # Virgin store: the first transaction must bootstrap it.
    engine = GitContentEngine(
        tmp_path / workspace_id, tmp_path / ".working_copies" / workspace_id
    )
    return KnowledgeStore(workspace_id, engine)


async def test_transaction_records_one_revision(store):
    async with store.transaction(message="add note", author=AUTHOR) as tx:
        tx.write("documents/note.xml", b"hello")

    assert tx.revision is not None
    assert await store.get_current_revision() == tx.revision
    assert await store.read_as_of(tx.revision, "documents/note.xml") == b"hello"


async def test_failed_transaction_records_nothing(store):
    with pytest.raises(RuntimeError):
        async with store.transaction(message="doomed", author=AUTHOR) as tx:
            tx.write("documents/note.xml", b"hello")
            raise RuntimeError("boom")

    assert await store.get_current_revision() is None


async def test_transaction_fails_while_another_writer_holds_the_workspace(
    store, workspace_id, short_lock_wait
):
    async with workspace_write_lock(workspace_id):
        with pytest.raises(KnowledgeStoreLockError):
            async with store.transaction(message="blocked", author=AUTHOR) as tx:
                tx.write("documents/note.xml", b"hello")

    assert await store.get_current_revision() is None
