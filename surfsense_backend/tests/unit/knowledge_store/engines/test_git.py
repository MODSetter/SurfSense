"""GitContentEngine: revision recording, history queries, and working copies.

Exercises the real engine (dulwich) against temp-dir repositories.
"""

from __future__ import annotations

import os
import time

import pytest

from app.knowledge_store.exceptions import GitPushError
from app.knowledge_store.engines.git import GitContentEngine

pytestmark = pytest.mark.unit

AUTHOR = "SurfSense <1@users.surfsense>"


class TestRecord:
    def test_empty_store_lists_no_revision(self, engine):
        assert engine.get_current_revision() is None
        assert engine.list_revisions() == []

    def test_record_returns_revision_and_advances_current_revision(self, engine):
        rev = engine.record(
            writes={"documents/a.xml": b"hello"},
            removes=[],
            message="add a",
            author=AUTHOR,
        )
        assert rev is not None
        assert engine.get_current_revision() == rev
        assert engine.read_as_of(rev, "documents/a.xml") == b"hello"

    def test_mixed_write_modify_delete_in_one_revision(self, engine):
        engine.record(
            writes={"keep.xml": b"k1", "mod.xml": b"m1", "del.xml": b"d1"},
            removes=[],
            message="seed",
            author=AUTHOR,
        )
        rev = engine.record(
            writes={"mod.xml": b"m2", "sub/new.xml": b"n1"},
            removes=["del.xml"],
            message="change",
            author=AUTHOR,
        )
        assert engine.read_as_of(rev, "keep.xml") == b"k1"
        assert engine.read_as_of(rev, "mod.xml") == b"m2"
        assert engine.read_as_of(rev, "sub/new.xml") == b"n1"
        with pytest.raises(KeyError):
            engine.read_as_of(rev, "del.xml")

    def test_noop_record_returns_none(self, engine):
        engine.record(
            writes={"a.xml": b"same"}, removes=[], message="one", author=AUTHOR
        )
        again = engine.record(
            writes={"a.xml": b"same"}, removes=[], message="two", author=AUTHOR
        )
        assert again is None

    def test_removing_untracked_path_is_tolerated(self, engine):
        rev = engine.record(
            writes={"a.xml": b"x"},
            removes=["never-existed.xml"],
            message="add a",
            author=AUTHOR,
        )
        assert rev is not None

    def test_deleted_folders_directory_does_not_linger(self, engine):
        # Git can't track empty dirs, so removing a folder's last file must also
        # drop the now-empty directory (and empty ancestors) from disk.
        engine.record(
            writes={"documents/f/sub/a.xml": b"a"},
            removes=[],
            message="seed nested",
            author=AUTHOR,
        )
        engine.record(
            writes={},
            removes=["documents/f/sub/a.xml"],
            message="delete last file",
            author=AUTHOR,
        )
        assert not (engine._path / "documents" / "f" / "sub").exists()
        assert not (engine._path / "documents" / "f").exists()

    def test_prune_keeps_dir_with_surviving_siblings(self, engine):
        engine.record(
            writes={"documents/f/a.xml": b"a", "documents/f/b.xml": b"b"},
            removes=[],
            message="seed",
            author=AUTHOR,
        )
        engine.record(
            writes={},
            removes=["documents/f/a.xml"],
            message="drop one",
            author=AUTHOR,
        )
        assert (engine._path / "documents" / "f" / "b.xml").is_file()


class TestHistoryQueries:
    def test_list_revisions_is_newest_first_and_path_scoped(self, engine):
        engine.record(writes={"a.xml": b"1"}, removes=[], message="a1", author=AUTHOR)
        engine.record(writes={"b.xml": b"1"}, removes=[], message="b1", author=AUTHOR)
        engine.record(writes={"a.xml": b"2"}, removes=[], message="a2", author=AUTHOR)

        all_msgs = [r.message for r in engine.list_revisions()]
        assert all_msgs == ["a2", "b1", "a1"]

        a_msgs = [r.message for r in engine.list_revisions(path="a.xml")]
        assert a_msgs == ["a2", "a1"]

        assert len(engine.list_revisions(limit=2)) == 2

    def test_revision_carries_author_and_timestamp(self, engine):
        engine.record(writes={"a.xml": b"1"}, removes=[], message="a1", author=AUTHOR)
        rev = engine.list_revisions()[0]
        assert rev.author == AUTHOR
        assert rev.created_at.tzinfo is not None

    def test_revision_distinguishes_author_from_committer(self, engine):
        agent = "SurfSense Agent <agent@surfsense>"
        engine.record(
            writes={"a.xml": b"1"},
            removes=[],
            message="a1",
            author=AUTHOR,
            committer=agent,
        )
        rev = engine.list_revisions()[0]
        assert rev.author == AUTHOR
        assert rev.committer == agent

    def test_committer_defaults_to_author(self, engine):
        engine.record(writes={"a.xml": b"1"}, removes=[], message="a1", author=AUTHOR)
        rev = engine.list_revisions()[0]
        assert rev.committer == AUTHOR

    def test_list_changes_reports_kinds_and_content_ids(self, engine):
        first = engine.record(
            writes={"a.xml": b"a1", "b.xml": b"b1"},
            removes=[],
            message="seed",
            author=AUTHOR,
        )
        second = engine.record(
            writes={"a.xml": b"a2", "c.xml": b"c1"},
            removes=["b.xml"],
            message="change",
            author=AUTHOR,
        )

        seeded = {c.path: c for c in engine.list_changes(first)}
        assert {p: c.kind for p, c in seeded.items()} == {
            "a.xml": "added",
            "b.xml": "added",
        }
        assert seeded["a.xml"].content_id == engine.compute_content_id(b"a1")

        changed = {c.path: c for c in engine.list_changes(second)}
        assert {p: c.kind for p, c in changed.items()} == {
            "a.xml": "modified",
            "b.xml": "removed",
            "c.xml": "added",
        }
        assert changed["a.xml"].content_id == engine.compute_content_id(b"a2")
        assert changed["b.xml"].content_id is None

    def test_list_changes_reports_a_move_as_one_rename(self, engine):
        """A move must not read as an unrelated removal and addition: the index
        would replace the document's row, cascading away its version history."""
        body = b"# Note\n\nenough body text for git to recognise it again\n"
        engine.record(
            writes={"old.xml": body}, removes=[], message="seed", author=AUTHOR
        )
        moved = engine.record(
            writes={"new.xml": body},
            removes=["old.xml"],
            message="move",
            author=AUTHOR,
        )

        (change,) = engine.list_changes(moved)
        assert (change.path, change.kind, change.previous_path) == (
            "new.xml",
            "renamed",
            "old.xml",
        )
        assert change.content_id == engine.compute_content_id(body)

    def test_a_move_that_rewrites_the_file_is_not_a_rename(self, engine):
        """The ceiling of matching by similarity: with nothing left in common there
        is no move to see, so the index falls back to replacing the row."""
        engine.record(
            writes={"old.xml": b"# Note\n\nthe original body\n"},
            removes=[],
            message="seed",
            author=AUTHOR,
        )
        rewritten = engine.record(
            writes={"new.xml": b"# Other\n\nnothing whatever in common\n"},
            removes=["old.xml"],
            message="rewrite",
            author=AUTHOR,
        )

        assert {c.path: c.kind for c in engine.list_changes(rewritten)} == {
            "old.xml": "removed",
            "new.xml": "added",
        }

    def test_list_changes_since_reports_a_window_net(self, engine):
        """What a queued index run needs: several revisions behind, it asks once
        for the net effect rather than replaying each revision and folding."""
        body = b"# Note\n\nenough body text for git to recognise it again\n"
        base = engine.record(
            writes={"old.xml": body}, removes=[], message="seed", author=AUTHOR
        )
        engine.record(
            writes={"new.xml": body, "gone.xml": b"transient"},
            removes=["old.xml"],
            message="move",
            author=AUTHOR,
        )
        head = engine.record(
            writes={"new.xml": body + b"edited later\n"},
            removes=["gone.xml"],
            message="edit",
            author=AUTHOR,
        )

        window = {c.path: c for c in engine.list_changes(head, since=base)}
        # The move survives being edited afterwards, and a file that came and went
        # inside the window is not reported at all.
        assert window["new.xml"].kind == "renamed"
        assert window["new.xml"].previous_path == "old.xml"
        assert "gone.xml" not in window

    def test_list_paths_reflects_the_given_revision(self, engine):
        first = engine.record(
            writes={"a.xml": b"a1", "sub/b.xml": b"b1"},
            removes=[],
            message="seed",
            author=AUTHOR,
        )
        second = engine.record(
            writes={"c.xml": b"c1"}, removes=["a.xml"], message="change", author=AUTHOR
        )

        assert {t.path for t in engine.list_paths(first)} == {"a.xml", "sub/b.xml"}
        latest = {t.path: t.content_id for t in engine.list_paths(second)}
        assert set(latest) == {"sub/b.xml", "c.xml"}
        assert latest["c.xml"] == engine.compute_content_id(b"c1")

    def test_compute_content_id_matches_git_hash_object(self, engine):
        # `printf hello | git hash-object --stdin`
        assert (
            engine.compute_content_id(b"hello")
            == "b6fc4c620b67d95f953a5c1c1230aaab5db5a1b0"
        )
        assert engine.compute_content_id(b"x") != engine.compute_content_id(b"y")


class TestWorkingCopies:
    def test_open_checks_out_current_content_and_reopens_in_place(self, engine):
        rev = engine.record(
            writes={"documents/a.xml": b"a1"}, removes=[], message="seed", author=AUTHOR
        )

        copy = engine.open_working_copy("turn-1")
        assert copy.base_revision == rev
        assert (copy.path / "documents/a.xml").read_bytes() == b"a1"

        (copy.path / "scratch.xml").write_bytes(b"s")
        reopened = engine.open_working_copy("turn-1")
        assert reopened.path == copy.path
        assert reopened.base_revision == rev
        assert (reopened.path / "scratch.xml").read_bytes() == b"s"

    def test_open_on_empty_store_yields_bare_directory(self, engine):
        copy = engine.open_working_copy("turn-1")
        assert copy.base_revision is None
        assert copy.path.is_dir()
        assert not (copy.path / ".git").exists()

    def test_parallel_copies_are_isolated(self, engine):
        engine.record(
            writes={"a.xml": b"a1"}, removes=[], message="seed", author=AUTHOR
        )
        one = engine.open_working_copy("turn-1")
        two = engine.open_working_copy("turn-2")

        (one.path / "a.xml").write_bytes(b"turn-1 edit")
        assert (two.path / "a.xml").read_bytes() == b"a1"

    def test_diff_reports_net_changes_against_base(self, engine):
        engine.record(
            writes={"keep.xml": b"k", "edit.xml": b"e1", "gone.xml": b"g"},
            removes=[],
            message="seed",
            author=AUTHOR,
        )
        copy = engine.open_working_copy("turn-1")
        (copy.path / "edit.xml").write_bytes(b"e2")
        (copy.path / "sub").mkdir()
        (copy.path / "sub/new.xml").write_bytes(b"n")
        (copy.path / "gone.xml").unlink()

        writes, removes = engine.diff_working_copy("turn-1")
        assert writes == {"edit.xml": b"e2", "sub/new.xml": b"n"}
        assert removes == ["gone.xml"]

    def test_diff_on_empty_base_reports_every_file_as_write(self, engine):
        copy = engine.open_working_copy("turn-1")
        (copy.path / "documents").mkdir()
        (copy.path / "documents/a.xml").write_bytes(b"a")

        writes, removes = engine.diff_working_copy("turn-1")
        assert writes == {"documents/a.xml": b"a"}
        assert removes == []

    def test_untouched_copy_diffs_to_nothing(self, engine):
        engine.record(writes={"a.xml": b"a"}, removes=[], message="seed", author=AUTHOR)
        engine.open_working_copy("turn-1")
        assert engine.diff_working_copy("turn-1") == ({}, [])

    def test_diff_of_an_unopened_copy_raises(self, engine):
        with pytest.raises(FileNotFoundError):
            engine.diff_working_copy("never-opened")

    def test_discard_removes_copy_and_tolerates_absence(self, engine):
        engine.record(writes={"a.xml": b"a"}, removes=[], message="seed", author=AUTHOR)
        copy = engine.open_working_copy("turn-1")
        engine.discard_working_copy("turn-1")
        assert not copy.path.exists()
        engine.discard_working_copy("turn-1")  # absent: no-op

    def test_prune_removes_only_stale_copies(self, engine):
        engine.record(writes={"a.xml": b"a"}, removes=[], message="seed", author=AUTHOR)
        stale = engine.open_working_copy("stale-turn")
        fresh = engine.open_working_copy("fresh-turn")
        old = time.time() - 3600
        os.utime(stale.path, (old, old))

        pruned = engine.prune_working_copies(older_than_seconds=1800)
        assert pruned == ["stale-turn"]
        assert not stale.path.exists()
        assert fresh.path.exists()


class TestPush:
    def test_push_to_empty_remote_copies_head(self, tmp_path):
        source = GitContentEngine(tmp_path / "a", tmp_path / "wc-a")
        dest = GitContentEngine(tmp_path / "b", tmp_path / "wc-b")
        dest._ensure_exists()
        rev = source.record(
            writes={"documents/a.md": b"hello"},
            removes=[],
            message="add a",
            author=AUTHOR,
        )
        pushed = source.push(
            url=str(dest._path),
            ref="refs/heads/main",
            username="git",
            password="x",
        )
        assert pushed == rev
        assert dest.read_as_of(rev, "documents/a.md") == b"hello"

    def test_non_fast_forward_raises_and_leaves_source_head(self, tmp_path):
        source = GitContentEngine(tmp_path / "a", tmp_path / "wc-a")
        dest = GitContentEngine(tmp_path / "b", tmp_path / "wc-b")
        source.record(
            writes={"documents/a.md": b"a"},
            removes=[],
            message="a",
            author=AUTHOR,
        )
        dest.record(
            writes={"documents/a.md": b"b"},
            removes=[],
            message="b",
            author=AUTHOR,
        )
        before = source.get_current_revision()
        with pytest.raises(GitPushError):
            source.push(
                url=str(dest._path),
                ref="refs/heads/master",
                username="git",
                password="x",
            )
        assert source.get_current_revision() == before

