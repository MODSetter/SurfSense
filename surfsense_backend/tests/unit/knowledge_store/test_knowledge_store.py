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
    s.ensure_exists()
    return s


class TestGitContentStore:
    def test_ensure_exists_is_idempotent(self, tmp_path):
        s = GitContentStore(tmp_path / "ws")
        s.ensure_exists()
        s.ensure_exists()
        assert (tmp_path / "ws" / ".git").is_dir()

    def test_empty_store_lists_no_revision(self, store):
        assert store.get_current_revision() is None
        assert store.list_revisions() == []

    def test_record_returns_revision_and_advances_current_revision(self, store):
        rev = store.record(
            writes={"documents/a.xml": b"hello"},
            removes=[],
            message="add a",
            author=AUTHOR,
        )
        assert rev is not None
        assert store.get_current_revision() == rev
        assert store.read_as_of(rev, "documents/a.xml") == b"hello"

    def test_mixed_write_modify_delete_in_one_revision(self, store):
        store.record(
            writes={"keep.xml": b"k1", "mod.xml": b"m1", "del.xml": b"d1"},
            removes=[],
            message="seed",
            author=AUTHOR,
        )
        rev = store.record(
            writes={"mod.xml": b"m2", "sub/new.xml": b"n1"},
            removes=["del.xml"],
            message="change",
            author=AUTHOR,
        )
        assert store.read_as_of(rev, "keep.xml") == b"k1"
        assert store.read_as_of(rev, "mod.xml") == b"m2"
        assert store.read_as_of(rev, "sub/new.xml") == b"n1"
        with pytest.raises(KeyError):
            store.read_as_of(rev, "del.xml")

    def test_noop_record_returns_none(self, store):
        store.record(
            writes={"a.xml": b"same"}, removes=[], message="one", author=AUTHOR
        )
        again = store.record(
            writes={"a.xml": b"same"}, removes=[], message="two", author=AUTHOR
        )
        assert again is None

    def test_removing_untracked_path_is_tolerated(self, store):
        rev = store.record(
            writes={"a.xml": b"x"},
            removes=["never-existed.xml"],
            message="add a",
            author=AUTHOR,
        )
        assert rev is not None

    def test_list_revisions_is_newest_first_and_path_scoped(self, store):
        store.record(writes={"a.xml": b"1"}, removes=[], message="a1", author=AUTHOR)
        store.record(writes={"b.xml": b"1"}, removes=[], message="b1", author=AUTHOR)
        store.record(writes={"a.xml": b"2"}, removes=[], message="a2", author=AUTHOR)

        all_msgs = [r.message for r in store.list_revisions()]
        assert all_msgs == ["a2", "b1", "a1"]

        a_msgs = [r.message for r in store.list_revisions(path="a.xml")]
        assert a_msgs == ["a2", "a1"]

        assert len(store.list_revisions(limit=2)) == 2

    def test_revision_carries_author_and_timestamp(self, store):
        store.record(writes={"a.xml": b"1"}, removes=[], message="a1", author=AUTHOR)
        rev = store.list_revisions()[0]
        assert rev.author == AUTHOR
        assert rev.created_at.tzinfo is not None

    def test_list_changes_reports_kinds_and_content_ids(self, store):
        first = store.record(
            writes={"a.xml": b"a1", "b.xml": b"b1"},
            removes=[],
            message="seed",
            author=AUTHOR,
        )
        second = store.record(
            writes={"a.xml": b"a2", "c.xml": b"c1"},
            removes=["b.xml"],
            message="change",
            author=AUTHOR,
        )

        seeded = {c.path: c for c in store.list_changes(first)}
        assert {p: c.kind for p, c in seeded.items()} == {
            "a.xml": "added",
            "b.xml": "added",
        }
        assert seeded["a.xml"].content_id == store.compute_content_id(b"a1")

        changed = {c.path: c for c in store.list_changes(second)}
        assert {p: c.kind for p, c in changed.items()} == {
            "a.xml": "modified",
            "b.xml": "removed",
            "c.xml": "added",
        }
        assert changed["a.xml"].content_id == store.compute_content_id(b"a2")
        assert changed["b.xml"].content_id is None

    def test_list_paths_reflects_the_given_revision(self, store):
        first = store.record(
            writes={"a.xml": b"a1", "sub/b.xml": b"b1"},
            removes=[],
            message="seed",
            author=AUTHOR,
        )
        second = store.record(
            writes={"c.xml": b"c1"}, removes=["a.xml"], message="change", author=AUTHOR
        )

        assert {t.path for t in store.list_paths(first)} == {"a.xml", "sub/b.xml"}
        latest = {t.path: t.content_id for t in store.list_paths(second)}
        assert set(latest) == {"sub/b.xml", "c.xml"}
        assert latest["c.xml"] == store.compute_content_id(b"c1")

    def test_compute_content_id_matches_git_hash_object(self, store):
        # `printf hello | git hash-object --stdin`
        assert store.compute_content_id(b"hello") == "b6fc4c620b67d95f953a5c1c1230aaab5db5a1b0"
        assert store.compute_content_id(b"x") != store.compute_content_id(b"y")


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

    async def test_transaction_write_records_one_revision(self, store):
        await store.ensure_exists()
        async with store.transaction(message="add", author=AUTHOR) as tx:
            tx.write("documents/a.xml", b"hi")

        rev = tx.revision
        assert rev == await store.get_current_revision()
        assert await store.read_as_of(rev, "documents/a.xml") == b"hi"
        assert [r.message for r in await store.list_revisions()] == ["add"]

    async def test_transaction_records_all_verbs_as_a_single_revision(self, store):
        await store.ensure_exists()
        async with store.transaction(message="seed", author=AUTHOR) as tx:
            tx.write("old.xml", b"content")
            tx.write("drop.xml", b"x")
        async with store.transaction(message="edit", author=AUTHOR) as tx:
            tx.move("old.xml", "new.xml")
            tx.remove("drop.xml")
            tx.write("extra.xml", b"y")

        rev = tx.revision
        assert await store.read_as_of(rev, "new.xml") == b"content"
        assert await store.read_as_of(rev, "extra.xml") == b"y"
        with pytest.raises(KeyError):
            await store.read_as_of(rev, "old.xml")
        with pytest.raises(KeyError):
            await store.read_as_of(rev, "drop.xml")
        # Two scopes -> exactly two revisions.
        assert len(await store.list_revisions()) == 2

    async def test_exception_in_scope_records_nothing(self, store):
        await store.ensure_exists()
        with pytest.raises(RuntimeError):
            async with store.transaction(message="nope", author=AUTHOR) as tx:
                tx.write("a.xml", b"x")
                raise RuntimeError("boom")

        assert await store.get_current_revision() is None
        assert tx.revision is None

    async def test_content_id_delegates_to_engine(self, store):
        assert store.compute_content_id(b"hi") == GitContentStore.compute_content_id(b"hi")
