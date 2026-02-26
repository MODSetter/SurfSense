"""
Integration tests for page-limit enforcement during document upload.

These tests manipulate the test user's ``pages_used`` / ``pages_limit``
columns directly in the database (setup only) and then exercise the upload
pipeline to verify that:

  - Uploads are rejected *before* ETL when the limit is exhausted.
  - ``pages_used`` increases after a successful upload (verified via API).
  - A ``page_limit_exceeded`` notification is created on rejection.
  - ``pages_used`` is not modified when a document fails processing.

All tests reuse the existing small fixtures (``sample.pdf``, ``sample.txt``)
so no additional processing time is introduced.

Prerequisites:
  - PostgreSQL + pgvector
"""

from __future__ import annotations

import httpx
import pytest

from tests.utils.helpers import (
    get_notifications,
    poll_document_status,
    upload_file,
)

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helper: read pages_used through the public API
# ---------------------------------------------------------------------------


async def _get_pages_used(client: httpx.AsyncClient, headers: dict[str, str]) -> int:
    """Fetch the current user's pages_used via the /users/me API."""
    resp = await client.get("/users/me", headers=headers)
    assert resp.status_code == 200, (
        f"GET /users/me failed ({resp.status_code}): {resp.text}"
    )
    return resp.json()["pages_used"]


# ---------------------------------------------------------------------------
# Test A: Successful upload increments pages_used
# ---------------------------------------------------------------------------


class TestPageUsageIncrementsOnSuccess:
    """After a successful PDF upload the user's ``pages_used`` must grow."""

    async def test_pages_used_increases_after_pdf_upload(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        search_space_id: int,
        cleanup_doc_ids: list[int],
        page_limits,
    ):
        await page_limits.set(pages_used=0, pages_limit=1000)

        resp = await upload_file(
            client, headers, "sample.pdf", search_space_id=search_space_id
        )
        assert resp.status_code == 200
        doc_ids = resp.json()["document_ids"]
        cleanup_doc_ids.extend(doc_ids)

        statuses = await poll_document_status(
            client, headers, doc_ids, search_space_id=search_space_id, timeout=300.0
        )
        for did in doc_ids:
            assert statuses[did]["status"]["state"] == "ready"

        used = await _get_pages_used(client, headers)
        assert used > 0, "pages_used should have increased after successful processing"


# ---------------------------------------------------------------------------
# Test B: Upload rejected when page limit is fully exhausted
# ---------------------------------------------------------------------------


class TestUploadRejectedWhenLimitExhausted:
    """
    When ``pages_used == pages_limit`` (zero remaining) the document
    should reach ``failed`` status with a page-limit reason.
    """

    async def test_pdf_fails_when_no_pages_remaining(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        search_space_id: int,
        cleanup_doc_ids: list[int],
        page_limits,
    ):
        await page_limits.set(pages_used=100, pages_limit=100)

        resp = await upload_file(
            client, headers, "sample.pdf", search_space_id=search_space_id
        )
        assert resp.status_code == 200
        doc_ids = resp.json()["document_ids"]
        cleanup_doc_ids.extend(doc_ids)

        statuses = await poll_document_status(
            client, headers, doc_ids, search_space_id=search_space_id, timeout=300.0
        )
        for did in doc_ids:
            assert statuses[did]["status"]["state"] == "failed"
            reason = statuses[did]["status"].get("reason", "").lower()
            assert "page limit" in reason, (
                f"Expected 'page limit' in failure reason, got: {reason!r}"
            )

    async def test_pages_used_unchanged_after_limit_rejection(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        search_space_id: int,
        cleanup_doc_ids: list[int],
        page_limits,
    ):
        await page_limits.set(pages_used=50, pages_limit=50)

        resp = await upload_file(
            client, headers, "sample.pdf", search_space_id=search_space_id
        )
        assert resp.status_code == 200
        doc_ids = resp.json()["document_ids"]
        cleanup_doc_ids.extend(doc_ids)

        await poll_document_status(
            client, headers, doc_ids, search_space_id=search_space_id, timeout=300.0
        )

        used = await _get_pages_used(client, headers)
        assert used == 50, (
            f"pages_used should remain 50 after rejected upload, got {used}"
        )


# ---------------------------------------------------------------------------
# Test C: Page-limit notification is created on rejection
# ---------------------------------------------------------------------------


class TestPageLimitNotification:
    """A ``page_limit_exceeded`` notification must be created when upload
    is rejected due to the limit."""

    async def test_page_limit_exceeded_notification_created(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        search_space_id: int,
        cleanup_doc_ids: list[int],
        page_limits,
    ):
        await page_limits.set(pages_used=100, pages_limit=100)

        resp = await upload_file(
            client, headers, "sample.pdf", search_space_id=search_space_id
        )
        assert resp.status_code == 200
        doc_ids = resp.json()["document_ids"]
        cleanup_doc_ids.extend(doc_ids)

        await poll_document_status(
            client, headers, doc_ids, search_space_id=search_space_id, timeout=300.0
        )

        notifications = await get_notifications(
            client,
            headers,
            type_filter="page_limit_exceeded",
            search_space_id=search_space_id,
        )
        assert len(notifications) >= 1, (
            "Expected at least one page_limit_exceeded notification"
        )

        latest = notifications[0]
        assert (
            "page limit" in latest["title"].lower()
            or "page limit" in latest["message"].lower()
        ), (
            f"Notification should mention page limit: title={latest['title']!r}, "
            f"message={latest['message']!r}"
        )


# ---------------------------------------------------------------------------
# Test D: Successful upload creates a completed document_processing notification
# ---------------------------------------------------------------------------


class TestDocumentProcessingNotification:
    """A ``document_processing`` notification with ``completed`` status must
    exist after a successful upload."""

    async def test_processing_completed_notification_exists(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        search_space_id: int,
        cleanup_doc_ids: list[int],
        page_limits,
    ):
        await page_limits.set(pages_used=0, pages_limit=1000)

        resp = await upload_file(
            client, headers, "sample.txt", search_space_id=search_space_id
        )
        assert resp.status_code == 200
        doc_ids = resp.json()["document_ids"]
        cleanup_doc_ids.extend(doc_ids)

        await poll_document_status(
            client, headers, doc_ids, search_space_id=search_space_id
        )

        notifications = await get_notifications(
            client,
            headers,
            type_filter="document_processing",
            search_space_id=search_space_id,
        )
        completed = [
            n
            for n in notifications
            if n.get("metadata", {}).get("processing_stage") == "completed"
        ]
        assert len(completed) >= 1, (
            "Expected at least one document_processing notification with 'completed' stage"
        )


# ---------------------------------------------------------------------------
# Test E: pages_used unchanged when a document fails for non-limit reasons
# ---------------------------------------------------------------------------


class TestPagesUnchangedOnProcessingFailure:
    """If a document fails during ETL (e.g. empty/corrupt file) rather than
    a page-limit rejection, ``pages_used`` should remain unchanged."""

    async def test_pages_used_stable_on_etl_failure(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        search_space_id: int,
        cleanup_doc_ids: list[int],
        page_limits,
    ):
        await page_limits.set(pages_used=10, pages_limit=1000)

        resp = await upload_file(
            client, headers, "empty.pdf", search_space_id=search_space_id
        )
        assert resp.status_code == 200
        doc_ids = resp.json()["document_ids"]
        cleanup_doc_ids.extend(doc_ids)

        if doc_ids:
            statuses = await poll_document_status(
                client, headers, doc_ids, search_space_id=search_space_id, timeout=120.0
            )
            for did in doc_ids:
                assert statuses[did]["status"]["state"] == "failed"

        used = await _get_pages_used(client, headers)
        assert used == 10, f"pages_used should remain 10 after ETL failure, got {used}"


# ---------------------------------------------------------------------------
# Test F: Second upload rejected after first consumes remaining quota
# ---------------------------------------------------------------------------


class TestSecondUploadExceedsLimit:
    """Upload one PDF successfully, consuming the quota, then verify a
    second upload is rejected."""

    async def test_second_upload_rejected_after_quota_consumed(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        search_space_id: int,
        cleanup_doc_ids: list[int],
        page_limits,
    ):
        await page_limits.set(pages_used=0, pages_limit=1)

        resp1 = await upload_file(
            client, headers, "sample.pdf", search_space_id=search_space_id
        )
        assert resp1.status_code == 200
        first_ids = resp1.json()["document_ids"]
        cleanup_doc_ids.extend(first_ids)

        statuses1 = await poll_document_status(
            client, headers, first_ids, search_space_id=search_space_id, timeout=300.0
        )
        for did in first_ids:
            assert statuses1[did]["status"]["state"] == "ready"

        resp2 = await upload_file(
            client,
            headers,
            "sample.pdf",
            search_space_id=search_space_id,
            filename_override="sample_copy.pdf",
        )
        assert resp2.status_code == 200
        second_ids = resp2.json()["document_ids"]
        cleanup_doc_ids.extend(second_ids)

        statuses2 = await poll_document_status(
            client, headers, second_ids, search_space_id=search_space_id, timeout=300.0
        )
        for did in second_ids:
            assert statuses2[did]["status"]["state"] == "failed"
            reason = statuses2[did]["status"].get("reason", "").lower()
            assert "page limit" in reason, (
                f"Expected 'page limit' in failure reason, got: {reason!r}"
            )
