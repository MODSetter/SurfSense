"""Unit tests for document-processing presentation logic."""

from __future__ import annotations

import pytest

from app.notifications.service.messages import document_processing as msg

pytestmark = pytest.mark.unit


def test_operation_id_encodes_type_and_space():
    """The operation id embeds the document type and search space id."""
    op = msg.operation_id("FILE", "report.pdf", 9)
    assert op.startswith("doc_FILE_9_")


@pytest.mark.parametrize(
    ("stage", "expected"),
    [
        ("parsing", "Reading your file"),
        ("chunking", "Preparing for search"),
        ("embedding", "Preparing for search"),
        ("storing", "Finalizing"),
        ("unknown", "Processing"),
    ],
)
def test_progress_stage_messages(stage, expected):
    """Each processing stage maps to its message; unknown stages get a fallback."""
    message, meta = msg.progress(stage)
    assert message == expected
    assert meta["processing_stage"] == stage


def test_progress_records_chunks_count():
    """A provided chunk count is stored in metadata for debugging."""
    _, meta = msg.progress("chunking", chunks_count=12)
    assert meta["chunks_count"] == 12


def test_progress_message_override():
    """An explicit stage message overrides the stage mapping."""
    message, _ = msg.progress("parsing", stage_message="Scanning")
    assert message == "Scanning"


def test_completion_success():
    """A successful run reports ready/completed and records the document id."""
    title, message, status, meta = msg.completion("report.pdf", document_id=5)
    assert title == "Ready: report.pdf"
    assert message == "Now searchable!"
    assert status == "completed"
    assert meta["document_id"] == 5
    assert meta["processing_stage"] == "completed"


def test_completion_failure():
    """An error reports failed status with the error surfaced in the message."""
    title, message, status, meta = msg.completion("report.pdf", error_message="bad")
    assert title == "Failed: report.pdf"
    assert message == "Processing failed: bad"
    assert status == "failed"
    assert meta["processing_stage"] == "failed"
