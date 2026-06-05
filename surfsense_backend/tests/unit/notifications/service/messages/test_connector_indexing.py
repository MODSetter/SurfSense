"""Unit tests for connector-indexing presentation logic."""

from __future__ import annotations

import pytest

from app.notifications.service.messages import connector_indexing as msg

pytestmark = pytest.mark.unit


class TestOperationId:
    def test_encodes_connector_id(self):
        """The operation id embeds the connector id."""
        assert msg.operation_id(42).startswith("connector_42_")

    def test_appends_date_range_when_given(self):
        """A start/end date range is appended to the operation id."""
        op = msg.operation_id(42, start_date="2024-01-01", end_date="2024-02-01")
        assert op.endswith("_2024-01-01_2024-02-01")

    def test_uses_none_placeholder_for_open_ended_range(self):
        """A missing range bound is encoded as the 'none' placeholder."""
        assert msg.operation_id(42, start_date="2024-01-01").endswith(
            "_2024-01-01_none"
        )

    def test_google_drive_encodes_counts(self):
        """The Drive operation id embeds connector id plus folder/file counts."""
        op = msg.google_drive_operation_id(7, folder_count=2, file_count=5)
        assert op.startswith("drive_7_")
        assert op.endswith("_2f_5files")


class TestProgress:
    def test_known_stage_maps_to_message(self):
        """A known stage maps to its user-facing message and is recorded."""
        message, meta = msg.progress(3, stage="fetching")
        assert message == "Fetching your content"
        assert meta["indexed_count"] == 3
        assert meta["sync_stage"] == "fetching"

    def test_unknown_stage_falls_back_to_processing(self):
        """An unrecognized stage falls back to a generic 'Processing' message."""
        message, _ = msg.progress(1, stage="weird")
        assert message == "Processing"

    def test_stage_message_overrides_mapping(self):
        """An explicit stage message overrides the stage-to-message mapping."""
        message, _ = msg.progress(1, stage="fetching", stage_message="Custom")
        assert message == "Custom"

    def test_no_stage_uses_legacy_default(self):
        """With neither stage nor message, the legacy default message is used."""
        message, meta = msg.progress(1)
        assert message == "Fetching your content"
        assert "sync_stage" not in meta

    def test_total_count_yields_percent(self):
        """Supplying a total count produces a progress percentage."""
        _, meta = msg.progress(5, total_count=10)
        assert meta["total_count"] == 10
        assert meta["progress_percent"] == 50


class TestRetry:
    def test_strips_workspace_suffix_from_connector_name(self):
        """The provider name is derived by stripping the workspace suffix."""
        message, _ = msg.retry("Notion - My Workspace", 0, "rate_limit", 1, 3)
        assert message == "Notion rate limit reached. Retrying..."

    def test_explicit_service_name_wins(self):
        """An explicit service name overrides the connector-derived name."""
        message, _ = msg.retry(
            "Notion - WS", 0, "rate_limit", 1, 3, service_name="Slack"
        )
        assert message.startswith("Slack rate limit reached")

    @pytest.mark.parametrize(
        ("reason", "expected"),
        [
            ("rate_limit", "Notion rate limit reached"),
            ("server_error", "Notion is slow to respond"),
            ("timeout", "Notion took too long"),
            ("temporary_error", "Notion temporarily unavailable"),
            ("something_else", "Waiting for Notion"),
        ],
    )
    def test_reason_wording(self, reason, expected):
        """Each retry reason maps to its wording; unknown reasons get a fallback."""
        message, _ = msg.retry("Notion", 0, reason, 1, 3)
        assert message.startswith(expected)

    def test_long_wait_shows_seconds(self):
        """A wait longer than the threshold surfaces the retry delay in seconds."""
        message, _ = msg.retry("Notion", 0, "rate_limit", 1, 3, wait_seconds=10)
        assert "Retrying in 10s..." in message

    def test_short_wait_is_hidden(self):
        """A short wait is not worth showing, so no seconds are surfaced."""
        message, _ = msg.retry("Notion", 0, "rate_limit", 1, 3, wait_seconds=3)
        assert message.endswith("Retrying...")

    def test_synced_count_suffix_singular_and_plural(self):
        """Already-synced items are appended with correct singular/plural wording."""
        one, _ = msg.retry("Notion", 1, "rate_limit", 1, 3)
        many, _ = msg.retry("Notion", 2, "rate_limit", 1, 3)
        assert one.endswith("(1 item synced so far)")
        assert many.endswith("(2 items synced so far)")

    def test_metadata_records_retry_state(self):
        """Retry metadata captures the attempt, reason, and wait state."""
        _, meta = msg.retry("Notion", 0, "rate_limit", 2, 5, wait_seconds=8)
        assert meta["sync_stage"] == "waiting_retry"
        assert meta["retry_attempt"] == 2
        assert meta["retry_max_attempts"] == 5
        assert meta["retry_reason"] == "rate_limit"
        assert meta["retry_wait_seconds"] == 8


class TestCompletion:
    def test_clean_success_plural(self):
        """A clean multi-file sync reports ready/completed with plural wording."""
        title, message, status, meta = msg.completion("GitHub", 3)
        assert title == "Ready: GitHub"
        assert message == "Now searchable! 3 files synced."
        assert status == "completed"
        assert meta["sync_stage"] == "completed"

    def test_clean_success_singular(self):
        """A single synced file uses singular 'file' wording."""
        _, message, _, _ = msg.completion("GitHub", 1)
        assert message == "Now searchable! 1 file synced."

    def test_nothing_to_sync(self):
        """Zero new items with no error reports 'Already up to date!'."""
        _, message, status, _ = msg.completion("GitHub", 0)
        assert message == "Already up to date!"
        assert status == "completed"

    def test_hard_failure(self):
        """An error with nothing synced reports a hard failure."""
        title, message, status, meta = msg.completion("GitHub", 0, error_message="boom")
        assert title == "Failed: GitHub"
        assert message == "Sync failed: boom"
        assert status == "failed"
        assert meta["sync_stage"] == "failed"

    def test_partial_success_with_error_note(self):
        """An error after partial progress still completes, with an appended note."""
        title, message, status, _ = msg.completion("GitHub", 2, error_message="flaky")
        assert title == "Ready: GitHub"
        assert message == "Now searchable! 2 files synced. Note: flaky"
        assert status == "completed"

    def test_warning_is_treated_as_complete(self):
        """A warning-level error completes the run rather than failing it."""
        title, message, status, _ = msg.completion(
            "GitHub", 0, error_message="partial", is_warning=True
        )
        assert title == "Ready: GitHub"
        assert message == "Sync complete. partial"
        assert status == "completed"

    def test_unsupported_files_note_singular_and_plural(self):
        """Unsupported-file counts are described with correct singular/plural wording."""
        _, one, _, _ = msg.completion("GitHub", 2, unsupported_count=1)
        _, many, _, _ = msg.completion("GitHub", 2, unsupported_count=3)
        assert "1 file was not supported." in one
        assert "3 files were not supported." in many

    def test_zero_indexed_with_unsupported_reports_complete(self):
        """Nothing synced but some unsupported files still reports completion."""
        _, message, status, _ = msg.completion("GitHub", 0, unsupported_count=2)
        assert message == "Sync complete. 2 files were not supported."
        assert status == "completed"
