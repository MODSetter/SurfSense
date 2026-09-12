"""3-way md bijection: observable apply/conflict, no git."""

from __future__ import annotations

import pytest

from app.knowledge_store.remote.planner import FileChange, SyncConflict, SyncPlan, plan

pytestmark = pytest.mark.unit


def test_remote_edit_applies_when_local_still_matches_base():
    result = plan(
        base={"a.md": b"old"},
        local={"a.md": b"old"},
        remote={"a.md": b"new"},
    )
    assert result == SyncPlan(apply_local=(FileChange("a.md", b"new"),))


def test_local_edit_is_kept_when_remote_still_matches_base():
    result = plan(
        base={"a.md": b"old"},
        local={"a.md": b"mine"},
        remote={"a.md": b"old"},
    )
    assert result == SyncPlan(apply_local=())


def test_both_sides_editing_the_same_path_is_a_conflict():
    result = plan(
        base={"a.md": b"old"},
        local={"a.md": b"mine"},
        remote={"a.md": b"theirs"},
    )
    assert result == SyncConflict(paths=("a.md",))


def test_identical_edits_on_both_sides_need_no_apply():
    result = plan(
        base={"a.md": b"old"},
        local={"a.md": b"same"},
        remote={"a.md": b"same"},
    )
    assert result == SyncPlan(apply_local=())


def test_remote_delete_applies_when_local_still_matches_base():
    result = plan(
        base={"a.md": b"old"},
        local={"a.md": b"old"},
        remote={},
    )
    assert result == SyncPlan(apply_local=(FileChange("a.md", None),))


def test_local_delete_and_remote_edit_is_a_conflict():
    result = plan(
        base={"a.md": b"old"},
        local={},
        remote={"a.md": b"theirs"},
    )
    assert result == SyncConflict(paths=("a.md",))


def test_a_conflict_blocks_every_other_path():
    result = plan(
        base={"a.md": b"old", "b.md": b"b"},
        local={"a.md": b"mine", "b.md": b"b"},
        remote={"a.md": b"theirs", "b.md": b"remote-b"},
    )
    assert result == SyncConflict(paths=("a.md",))
