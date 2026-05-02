"""Unit tests for the edit-from-arbitrary-position helpers inside ``new_chat_routes``.

The regenerate route's edit-from-position path introduces:
* ``_find_pre_turn_checkpoint_id`` — walks LangGraph checkpoint tuples
  newest-first and picks the first one whose ``metadata["turn_id"]``
  differs from the edited turn. That checkpoint is the rewind target
  (state immediately before the edited turn started).
* ``RegenerateRequest`` accepts ``from_message_id`` + ``revert_actions``
  with a validator that prevents callers from requesting a revert pass
  without specifying which turn to roll back.

These are pure-Python helpers that don't need a live DB, so we exercise
them with a small ``CheckpointTuple``-shaped namespace and direct
schema instantiation.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.routes.new_chat_routes import _find_pre_turn_checkpoint_id
from app.schemas.new_chat import RegenerateRequest


def _cp(checkpoint_id: str, turn_id: str | None) -> SimpleNamespace:
    """Build a fake ``CheckpointTuple`` with the metadata shape we read."""
    return SimpleNamespace(
        config={"configurable": {"checkpoint_id": checkpoint_id}},
        metadata={"turn_id": turn_id} if turn_id is not None else {},
    )


class TestFindPreTurnCheckpointId:
    def test_returns_last_pre_turn_checkpoint_when_editing_latest_turn(self) -> None:
        # Newest-first: T2 is the most-recent turn. The latest non-T2
        # checkpoint (cp2) is the rewind target — state immediately
        # before T2 began.
        tuples = [
            _cp("cp4", "T2"),
            _cp("cp3", "T2"),
            _cp("cp2", "T1"),
            _cp("cp1", "T1"),
        ]
        assert _find_pre_turn_checkpoint_id(tuples, turn_id="T2") == "cp2"

    def test_returns_pre_turn_checkpoint_when_later_turns_exist(self) -> None:
        # Regression for the bug where walking newest-first returned the
        # FIRST cp with ``turn_id != target`` — which is one of the
        # later-turn checkpoints, NOT the pre-turn boundary. Editing
        # T2 must rewind to the latest T1 checkpoint (cp2), not to the
        # latest T3 checkpoint (cp6).
        tuples = [
            _cp("cp6", "T3"),
            _cp("cp5", "T3"),
            _cp("cp4", "T2"),
            _cp("cp3", "T2"),
            _cp("cp2", "T1"),
            _cp("cp1", "T1"),
        ]
        assert _find_pre_turn_checkpoint_id(tuples, turn_id="T2") == "cp2"

    def test_returns_none_when_editing_first_turn(self) -> None:
        # No pre-turn boundary exists; caller is expected to fall back
        # to the oldest checkpoint or special-case "first turn of the
        # thread".
        tuples = [
            _cp("cp4", "T2"),
            _cp("cp3", "T2"),
            _cp("cp2", "T1"),
            _cp("cp1", "T1"),
        ]
        assert _find_pre_turn_checkpoint_id(tuples, turn_id="T1") is None

    def test_returns_none_when_only_edited_turn_present(self) -> None:
        tuples = [_cp("cp2", "T2"), _cp("cp1", "T2")]
        assert _find_pre_turn_checkpoint_id(tuples, turn_id="T2") is None

    def test_returns_none_for_empty_history(self) -> None:
        assert _find_pre_turn_checkpoint_id([], turn_id="T1") is None

    def test_legacy_checkpoints_without_turn_id_count_as_pre_turn(self) -> None:
        # Checkpoints written before migration 136 have no
        # ``metadata.turn_id``. They should be eligible rewind targets
        # — they came before the
        # edited turn began.
        tuples = [
            _cp("cp3", "T2"),
            SimpleNamespace(
                config={"configurable": {"checkpoint_id": "cp2"}},
                metadata=None,
            ),
            _cp("cp1", "T1"),
        ]
        # Walking oldest-first: cp1(T1) tracked, cp2(legacy/None) tracked,
        # then cp3(T2) crosses the boundary -> return cp2.
        assert _find_pre_turn_checkpoint_id(tuples, turn_id="T2") == "cp2"

    def test_skips_checkpoint_missing_checkpoint_id_in_config(self) -> None:
        # If a checkpoint tuple's ``config["configurable"]`` is missing
        # the ``checkpoint_id`` key (corrupt / partial), we keep the
        # last known good target instead of crashing.
        broken = SimpleNamespace(
            config={"configurable": {}}, metadata={"turn_id": "T1"}
        )
        tuples = [
            _cp("cp3", "T2"),
            broken,
            _cp("cp1", "T1"),
        ]
        # cp1(T1) tracked, broken skipped, cp3(T2) -> return cp1.
        assert _find_pre_turn_checkpoint_id(tuples, turn_id="T2") == "cp1"


class TestRegenerateRequestValidation:
    def test_revert_actions_requires_from_message_id(self) -> None:
        with pytest.raises(Exception) as exc:
            RegenerateRequest(
                search_space_id=1,
                user_query="hi",
                revert_actions=True,
            )
        msg = str(exc.value).lower()
        assert "from_message_id" in msg

    def test_from_message_id_without_revert_is_allowed(self) -> None:
        req = RegenerateRequest(
            search_space_id=1,
            user_query="hi",
            from_message_id=42,
        )
        assert req.from_message_id == 42
        assert req.revert_actions is False

    def test_revert_actions_with_from_message_id_passes(self) -> None:
        req = RegenerateRequest(
            search_space_id=1,
            user_query="hi",
            from_message_id=42,
            revert_actions=True,
        )
        assert req.revert_actions is True
