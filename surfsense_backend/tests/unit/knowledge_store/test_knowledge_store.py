"""Knowledge-store core: git engine behavior, the write-lock wrapper, and the
async facade. Uses a real git repo in a temp dir; no DB or Redis required."""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest

from app.knowledge_store.backends.git import GitContentStore
from app.knowledge_store.store import KnowledgeStore
from app.knowledge_store.write_lock import (
    KnowledgeStoreLockError,
    workspace_write_lock,
)

pytestmark = pytest.mark.unit

AUTHOR = "SurfSense <1@users.surfsense>"


@pytest.fixture
def store(tmp_path) -> GitContentStore:
    s = GitContentStore(tmp_path / "ws1")
    s.ensure()
    return s


class TestGitContentStore:
    def test_ensure_is_idempotent(self, tmp_path):
        s = GitContentStore(tmp_path / "ws")
        s.ensure()
        s.ensure()
        assert (tmp_path / "ws" / ".git").is_dir()

    def test_empty_store_has_no_current_revision_or_history(self, store):
        assert store.current_revision() is None
        assert store.history() == []

    def test_commit_returns_revision_and_advances_current_revision(self, store):
        rev = store.commit(
            writes={"documents/a.xml": b"hello"},
            removes=[],
            message="add a",
            author=AUTHOR,
        )
        assert rev is not None
        assert store.current_revision() == rev
        assert store.read_at(rev, "documents/a.xml") == b"hello"

    def test_mixed_write_modify_delete_in_one_revision(self, store):
        store.commit(
            writes={"keep.xml": b"k1", "mod.xml": b"m1", "del.xml": b"d1"},
            removes=[],
            message="seed",
            author=AUTHOR,
        )
        rev = store.commit(
            writes={"mod.xml": b"m2", "sub/new.xml": b"n1"},
            removes=["del.xml"],
            message="change",
            author=AUTHOR,
        )
        assert store.read_at(rev, "keep.xml") == b"k1"
        assert store.read_at(rev, "mod.xml") == b"m2"
        assert store.read_at(rev, "sub/new.xml") == b"n1"
        with pytest.raises(KeyError):
            store.read_at(rev, "del.xml")

    def test_noop_commit_returns_none(self, store):
        store.commit(
            writes={"a.xml": b"same"}, removes=[], message="one", author=AUTHOR
        )
        again = store.commit(
            writes={"a.xml": b"same"}, removes=[], message="two", author=AUTHOR
        )
        assert again is None

    def test_removing_untracked_path_is_tolerated(self, store):
        rev = store.commit(
            writes={"a.xml": b"x"},
            removes=["never-existed.xml"],
            message="add a",
            author=AUTHOR,
        )
        assert rev is not None

    def test_history_is_newest_first_and_path_scoped(self, store):
        store.commit(writes={"a.xml": b"1"}, removes=[], message="a1", author=AUTHOR)
        store.commit(writes={"b.xml": b"1"}, removes=[], message="b1", author=AUTHOR)
        store.commit(writes={"a.xml": b"2"}, removes=[], message="a2", author=AUTHOR)

        all_msgs = [r.message for r in store.history()]
        assert all_msgs == ["a2", "b1", "a1"]

        a_msgs = [r.message for r in store.history(path="a.xml")]
        assert a_msgs == ["a2", "a1"]

        assert len(store.history(limit=2)) == 2

    def test_revision_carries_author_and_timestamp(self, store):
        store.commit(writes={"a.xml": b"1"}, removes=[], message="a1", author=AUTHOR)
        rev = store.history()[0]
        assert rev.author == AUTHOR
        assert rev.created_at.tzinfo is not None

    def test_content_id_matches_git_hash_object(self, store):
        # `printf hello | git hash-object --stdin`
        assert store.content_id(b"hello") == "b6fc4c620b67d95f953a5c1c1230aaab5db5a1b0"
        assert store.content_id(b"x") != store.content_id(b"y")


class TestWorkspaceWriteLock:
    async def test_raises_when_lock_not_acquired(self, monkeypatch):
        class _Lock:
            async def acquire(self):
                return False

            async def release(self):
                pass

        class _Client:
            def lock(self, *_, **__):
                return _Lock()

        monkeypatch.setattr("app.knowledge_store.write_lock._redis", lambda: _Client())
        with pytest.raises(KnowledgeStoreLockError):
            async with workspace_write_lock("ws1"):
                pass

    async def test_yields_and_releases_when_acquired(self, monkeypatch):
        released = []

        class _Lock:
            async def acquire(self):
                return True

            async def release(self):
                released.append(True)

        class _Client:
            def lock(self, *_, **__):
                return _Lock()

        monkeypatch.setattr("app.knowledge_store.write_lock._redis", lambda: _Client())
        entered = False
        async with workspace_write_lock("ws1"):
            entered = True
        assert entered
        assert released == [True]


class TestKnowledgeStoreFacade:
    @pytest.fixture
    def store(self, tmp_path, monkeypatch):
        # Neutralize the Redis lock so the facade is exercised without infra.
        @asynccontextmanager
        async def _no_lock(_workspace_id):
            yield

        monkeypatch.setattr(
            "app.knowledge_store.store.workspace_write_lock", _no_lock
        )
        return KnowledgeStore("ws1", GitContentStore(tmp_path / "ws1"))

    async def test_revise_write_records_one_revision(self, store):
        await store.ensure_exists()
        async with store.revise(message="add", author=AUTHOR) as draft:
            draft.write("documents/a.xml", b"hi")

        rev = draft.revision
        assert rev == await store.current_revision()
        assert await store.read_at(rev, "documents/a.xml") == b"hi"
        assert [r.message for r in await store.history()] == ["add"]

    async def test_revise_batches_verbs_into_a_single_revision(self, store):
        await store.ensure_exists()
        async with store.revise(message="seed", author=AUTHOR) as draft:
            draft.write("old.xml", b"content")
            draft.write("drop.xml", b"x")
        async with store.revise(message="edit", author=AUTHOR) as draft:
            draft.move("old.xml", "new.xml")
            draft.remove("drop.xml")
            draft.write("extra.xml", b"y")

        rev = draft.revision
        assert await store.read_at(rev, "new.xml") == b"content"
        assert await store.read_at(rev, "extra.xml") == b"y"
        with pytest.raises(KeyError):
            await store.read_at(rev, "old.xml")
        with pytest.raises(KeyError):
            await store.read_at(rev, "drop.xml")
        # Two scopes -> exactly two revisions.
        assert len(await store.history()) == 2

    async def test_exception_in_scope_records_nothing(self, store):
        await store.ensure_exists()
        with pytest.raises(RuntimeError):
            async with store.revise(message="nope", author=AUTHOR) as draft:
                draft.write("a.xml", b"x")
                raise RuntimeError("boom")

        assert await store.current_revision() is None
        assert draft.revision is None

    async def test_content_id_delegates_to_engine(self, store):
        assert store.content_id(b"hi") == GitContentStore.content_id(b"hi")
