"""Unit tests for pure notification metadata transitions."""

from __future__ import annotations

import pytest

from app.notifications.service.metadata import apply_update, start_metadata

pytestmark = pytest.mark.unit


class TestStartMetadata:
    def test_seeds_operation_and_progress_fields(self):
        """A new notification is seeded with operation id, in-progress status, and start time."""
        meta = start_metadata("op-1")
        assert meta["operation_id"] == "op-1"
        assert meta["status"] == "in_progress"
        assert "started_at" in meta

    def test_preserves_initial_fields(self):
        """Caller-provided initial metadata is carried through."""
        meta = start_metadata("op-1", {"connector_id": 7})
        assert meta["connector_id"] == 7

    def test_does_not_mutate_caller_dict(self):
        """Seeding returns a new dict without mutating the caller's input."""
        initial = {"connector_id": 7}
        start_metadata("op-1", initial)
        assert initial == {"connector_id": 7}


class TestApplyUpdate:
    def test_completed_stamps_completed_at(self):
        """A completed status records a completion timestamp."""
        meta = apply_update({"status": "in_progress"}, status="completed")
        assert meta["status"] == "completed"
        assert "completed_at" in meta

    def test_failed_stamps_completed_at(self):
        """A failed status also records a completion timestamp."""
        meta = apply_update({}, status="failed")
        assert "completed_at" in meta

    def test_in_progress_does_not_stamp_completed_at(self):
        """A non-terminal status leaves the completion timestamp unset."""
        meta = apply_update({}, status="in_progress")
        assert "completed_at" not in meta

    def test_merges_metadata_updates(self):
        """Metadata updates are merged into the existing metadata."""
        meta = apply_update({"a": 1}, metadata_updates={"b": 2})
        assert meta == {"a": 1, "b": 2}

    def test_updates_override_existing_keys(self):
        """Updates take precedence over existing keys on conflict."""
        meta = apply_update({"a": 1}, metadata_updates={"a": 9})
        assert meta["a"] == 9

    def test_does_not_mutate_caller_dict(self):
        """Applying updates returns a new dict without mutating the caller's input."""
        current = {"a": 1}
        apply_update(current, status="completed", metadata_updates={"b": 2})
        assert current == {"a": 1}
