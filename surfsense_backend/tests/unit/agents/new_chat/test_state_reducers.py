"""Tests for SurfSense filesystem state reducers."""

from __future__ import annotations

import pytest

from app.agents.new_chat.state_reducers import (
    _CLEAR,
    _add_unique_reducer,
    _dict_merge_with_tombstones_reducer,
    _initial_filesystem_state,
    _list_append_reducer,
    _replace_reducer,
)

pytestmark = pytest.mark.unit


class TestReplaceReducer:
    def test_right_wins_outright(self):
        assert _replace_reducer("a", "b") == "b"

    def test_none_right_returns_none(self):
        assert _replace_reducer("a", None) is None

    def test_none_left_returns_right(self):
        assert _replace_reducer(None, "b") == "b"


class TestAddUniqueReducer:
    def test_appends_unique_items(self):
        assert _add_unique_reducer(["a"], ["b", "c"]) == ["a", "b", "c"]

    def test_dedupes_against_left(self):
        assert _add_unique_reducer(["a", "b"], ["b", "c"]) == ["a", "b", "c"]

    def test_dedupes_within_right(self):
        assert _add_unique_reducer([], ["a", "a", "b"]) == ["a", "b"]

    def test_clear_anywhere_resets_and_reseeds_with_after_items(self):
        # _CLEAR semantics: only items AFTER the LAST _CLEAR are kept.
        result = _add_unique_reducer(["x", "y"], ["a", _CLEAR, "b", "c"])
        assert result == ["b", "c"]

    def test_multiple_clears_use_last(self):
        result = _add_unique_reducer(["x"], [_CLEAR, "a", _CLEAR, "b"])
        assert result == ["b"]

    def test_clear_only_resets_to_empty(self):
        assert _add_unique_reducer(["x", "y"], [_CLEAR]) == []

    def test_empty_right_keeps_left(self):
        assert _add_unique_reducer(["a"], []) == ["a"]
        assert _add_unique_reducer(["a"], None) == ["a"]


class TestListAppendReducer:
    def test_preserves_order_and_duplicates(self):
        result = _list_append_reducer([{"a": 1}], [{"b": 2}, {"a": 1}])
        assert result == [{"a": 1}, {"b": 2}, {"a": 1}]

    def test_clear_resets_keeping_after_items(self):
        result = _list_append_reducer([{"a": 1}], [{"old": 1}, _CLEAR, {"new": 2}])
        assert result == [{"new": 2}]


class TestDictMergeWithTombstones:
    def test_merges_keys(self):
        assert _dict_merge_with_tombstones_reducer({"a": 1}, {"b": 2}) == {
            "a": 1,
            "b": 2,
        }

    def test_none_value_deletes_key(self):
        result = _dict_merge_with_tombstones_reducer({"a": 1, "b": 2}, {"a": None})
        assert result == {"b": 2}

    def test_clear_resets_then_merges(self):
        result = _dict_merge_with_tombstones_reducer(
            {"a": 1, "b": 2}, {_CLEAR: True, "c": 3}
        )
        assert result == {"c": 3}

    def test_clear_keeps_only_post_clear_non_none(self):
        result = _dict_merge_with_tombstones_reducer(
            {"a": 1}, {_CLEAR: True, "b": 2, "c": None}
        )
        assert result == {"b": 2}

    def test_none_left_handled(self):
        assert _dict_merge_with_tombstones_reducer(None, {"a": 1, "b": None}) == {
            "a": 1
        }


class TestInitialFilesystemState:
    def test_default_shape(self):
        state = _initial_filesystem_state()
        assert state["cwd"] == "/documents"
        assert state["staged_dirs"] == []
        assert state["staged_dir_tool_calls"] == {}
        assert state["pending_moves"] == []
        assert state["pending_deletes"] == []
        assert state["pending_dir_deletes"] == []
        assert state["doc_id_by_path"] == {}
        assert state["dirty_paths"] == []
        assert state["dirty_path_tool_calls"] == {}
        assert state["kb_priority"] == []
        assert state["kb_matched_chunk_ids"] == {}
        assert state["kb_anon_doc"] is None
        assert state["tree_version"] == 0


class TestMultiEditSamePathCoalescing:
    """Multi-edit-same-path turns must coalesce into ONE binding record.

    The persistence body uses ``dirty_path_tool_calls[path]`` to find the
    tool_call_id that produced the current state on disk. Because
    ``dirty_paths`` dedupes via :func:`_add_unique_reducer` the second
    edit doesn't append a new path entry — and because
    ``_dict_merge_with_tombstones_reducer`` lets the right-hand side
    overwrite, the LATEST tool_call_id wins. That's the correct behavior
    for snapshotting: revert restores to the pre-mutation state, and
    multiple back-to-back edits in one turn coalesce into a single
    revisible op (the user sees ONE Revert button per turn-per-path,
    not N).
    """

    def test_dirty_paths_dedupes_repeated_writes(self):
        # ``_add_unique_reducer`` is applied to ``dirty_paths``. Two writes
        # to the same path produce one entry, not two.
        first = _add_unique_reducer([], ["/documents/a.md"])
        second = _add_unique_reducer(first, ["/documents/a.md"])
        assert second == ["/documents/a.md"]

    def test_dirty_path_tool_calls_keeps_latest_tool_call_id(self):
        # First write tags the path with tcid-1.
        merged = _dict_merge_with_tombstones_reducer({}, {"/documents/a.md": "tcid-1"})
        # Second write to the same path tags it with tcid-2 (latest wins).
        merged = _dict_merge_with_tombstones_reducer(
            merged, {"/documents/a.md": "tcid-2"}
        )
        assert merged == {"/documents/a.md": "tcid-2"}

    def test_rm_tombstones_dirty_path_tool_call(self):
        # ``rm`` writes ``{path: None}`` into dirty_path_tool_calls to
        # prevent a stale binding from leaking past the delete.
        merged = _dict_merge_with_tombstones_reducer(
            {"/documents/a.md": "tcid-1"}, {"/documents/a.md": None}
        )
        assert merged == {}
