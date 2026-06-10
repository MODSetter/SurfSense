"""Tests for pure observability helper functions."""

from __future__ import annotations

import pytest

from app.observability import metrics as ot_metrics, otel as ot

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _disable_otel(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.setenv("SURFSENSE_DISABLE_OTEL", "true")
    ot.reload_for_tests()
    yield
    ot.reload_for_tests()


@pytest.mark.parametrize(
    ("task_name", "expected"),
    [
        ("reindex_document", "reindex"),
        ("delete_document_background", "delete"),
        ("delete_folder_documents_background", "delete"),
        ("delete_search_space_background", "delete"),
        ("process_extension_document", "process"),
        ("process_youtube_video", "process"),
        ("process_file_upload", "process"),
        ("process_file_upload_with_document", "process"),
        ("process_circleback_meeting", "process"),
        ("generate_video_presentation", "generate"),
        ("generate_content_podcast", "generate"),
        ("cleanup_stale_indexing_notifications", "cleanup"),
        ("reconcile_pending_stripe_credit_purchases", "reconcile"),
        ("check_periodic_schedules", "check"),
        ("ai_sort_search_space", "ai"),
        ("index_notion_pages", "index"),
        ("index_github_repos", "index"),
        ("index_google_drive_files", "index"),
        ("index_composio_connector", "index"),
        ("index_obsidian_attachment", "index"),
        ("index_local_folder", "index"),
        ("index_uploaded_folder_files", "index"),
        ("noseparator", "noseparator"),
        ("", "unknown"),
    ],
)
def test_parse_celery_task_label(task_name: str, expected: str) -> None:
    assert ot_metrics.parse_celery_task_label(task_name) == expected


def test_parse_celery_task_label_handles_none() -> None:
    assert ot_metrics.parse_celery_task_label(None) == "unknown"


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (type("RateLimitError", (Exception,), {})(), "rate_limited"),
        (type("AuthenticationError", (Exception,), {})(), "auth_failed"),
        (type("QuotaInsufficientError", (Exception,), {})(), "quota_exhausted"),
        (TimeoutError(), "timeout"),
        (type("APIConnectionError", (Exception,), {})(), "network_failed"),
        (type("ServiceUnavailableError", (Exception,), {})(), "server_error"),
        (type("LockContentionError", (Exception,), {})(), "lock_contention"),
        (type("UnsupportedFormatError", (Exception,), {})(), "unsupported_format"),
        (type("ProviderError", (Exception,), {})(), "provider_error"),
        (RuntimeError("plain"), "unknown"),
    ],
)
def test_categorize_exception(exc: BaseException, expected: str) -> None:
    assert ot_metrics.categorize_exception(exc) == expected


def test_record_celery_queue_latency_noops_when_disabled() -> None:
    ot_metrics.record_celery_queue_latency(
        0.5,
        task_name="index_notion_pages",
        queue="surfsense.connectors",
        scheduled=False,
        operation="index",
    )


def test_add_event_noops_when_disabled() -> None:
    ot.add_event("test.event", {"value": 1})


def test_add_event_noops_without_current_span(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeTrace:
        @staticmethod
        def get_current_span():
            return None

    monkeypatch.setattr(ot, "_ENABLED", True)
    monkeypatch.setattr(ot, "_ot_trace", FakeTrace())

    ot.add_event("test.event", {"value": 1})
