"""
Integration tests for ETL credit enforcement during document upload.

These tests manipulate the test user's ``credit_micros_balance`` column
directly in the database (setup only) and then exercise the upload pipeline
to verify that:

  - Uploads are rejected *before* ETL when the wallet can't cover the cost.
  - The balance decreases after a successful upload (verified via API).
  - An ``insufficient_credits`` notification is created on rejection.
  - The balance is not modified when a document fails processing.

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
# Helper: read credit balance through the public API
# ---------------------------------------------------------------------------


async def _get_balance(client: httpx.AsyncClient, headers: dict[str, str]) -> int:
    """Fetch the current user's credit_micros_balance via the /users/me API."""
    resp = await client.get("/users/me", headers=headers)
    assert resp.status_code == 200, (
        f"GET /users/me failed ({resp.status_code}): {resp.text}"
    )
    return resp.json()["credit_micros_balance"]


# ---------------------------------------------------------------------------
# Test A: Successful upload decrements the balance
# ---------------------------------------------------------------------------


class TestBalanceDecrementsOnSuccess:
    """After a successful PDF upload the user's balance must shrink."""

    async def test_balance_decreases_after_pdf_upload(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        workspace_id: int,
        cleanup_doc_ids: list[int],
        credits,
    ):
        await credits.set(balance_micros=credits.pages(1000))
        before = await _get_balance(client, headers)

        resp = await upload_file(
            client, headers, "sample.pdf", workspace_id=workspace_id
        )
        assert resp.status_code == 200
        doc_ids = resp.json()["document_ids"]
        cleanup_doc_ids.extend(doc_ids)

        statuses = await poll_document_status(
            client, headers, doc_ids, workspace_id=workspace_id, timeout=300.0
        )
        for did in doc_ids:
            assert statuses[did]["status"]["state"] == "ready"

        after = await _get_balance(client, headers)
        assert after < before, "balance should have dropped after successful processing"


# ---------------------------------------------------------------------------
# Test B: Upload rejected when the wallet is empty
# ---------------------------------------------------------------------------


class TestUploadRejectedWhenCreditExhausted:
    """When the balance is zero the document should reach ``failed`` status
    with an insufficient-credit reason."""

    async def test_pdf_fails_when_no_credit_remaining(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        workspace_id: int,
        cleanup_doc_ids: list[int],
        credits,
    ):
        await credits.set(balance_micros=0)

        resp = await upload_file(
            client, headers, "sample.pdf", workspace_id=workspace_id
        )
        assert resp.status_code == 200
        doc_ids = resp.json()["document_ids"]
        cleanup_doc_ids.extend(doc_ids)

        statuses = await poll_document_status(
            client, headers, doc_ids, workspace_id=workspace_id, timeout=300.0
        )
        for did in doc_ids:
            assert statuses[did]["status"]["state"] == "failed"
            reason = statuses[did]["status"].get("reason", "").lower()
            assert "credit" in reason, (
                f"Expected 'credit' in failure reason, got: {reason!r}"
            )

    async def test_balance_unchanged_after_rejection(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        workspace_id: int,
        cleanup_doc_ids: list[int],
        credits,
    ):
        await credits.set(balance_micros=0)

        resp = await upload_file(
            client, headers, "sample.pdf", workspace_id=workspace_id
        )
        assert resp.status_code == 200
        doc_ids = resp.json()["document_ids"]
        cleanup_doc_ids.extend(doc_ids)

        await poll_document_status(
            client, headers, doc_ids, workspace_id=workspace_id, timeout=300.0
        )

        balance = await _get_balance(client, headers)
        assert balance == 0, (
            f"balance should remain 0 after rejected upload, got {balance}"
        )


# ---------------------------------------------------------------------------
# Test C: Insufficient-credits notification is created on rejection
# ---------------------------------------------------------------------------


class TestInsufficientCreditsNotification:
    """An ``insufficient_credits`` notification must be created when upload
    is rejected due to an empty wallet."""

    async def test_insufficient_credits_notification_created(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        workspace_id: int,
        cleanup_doc_ids: list[int],
        credits,
    ):
        await credits.set(balance_micros=0)

        resp = await upload_file(
            client, headers, "sample.pdf", workspace_id=workspace_id
        )
        assert resp.status_code == 200
        doc_ids = resp.json()["document_ids"]
        cleanup_doc_ids.extend(doc_ids)

        await poll_document_status(
            client, headers, doc_ids, workspace_id=workspace_id, timeout=300.0
        )

        notifications = await get_notifications(
            client,
            headers,
            type_filter="insufficient_credits",
            workspace_id=workspace_id,
        )
        assert len(notifications) >= 1, (
            "Expected at least one insufficient_credits notification"
        )

        latest = notifications[0]
        assert (
            "credit" in latest["title"].lower() or "credit" in latest["message"].lower()
        ), (
            f"Notification should mention credit: title={latest['title']!r}, "
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
        workspace_id: int,
        cleanup_doc_ids: list[int],
        credits,
    ):
        await credits.set(balance_micros=credits.pages(1000))

        resp = await upload_file(
            client, headers, "sample.txt", workspace_id=workspace_id
        )
        assert resp.status_code == 200
        doc_ids = resp.json()["document_ids"]
        cleanup_doc_ids.extend(doc_ids)

        await poll_document_status(client, headers, doc_ids, workspace_id=workspace_id)

        notifications = await get_notifications(
            client,
            headers,
            type_filter="document_processing",
            workspace_id=workspace_id,
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
# Test E: balance unchanged when a document fails for non-credit reasons
# ---------------------------------------------------------------------------


class TestBalanceUnchangedOnProcessingFailure:
    """If a document fails during ETL (e.g. empty/corrupt file) rather than a
    credit rejection, the balance should remain unchanged."""

    async def test_balance_stable_on_etl_failure(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        workspace_id: int,
        cleanup_doc_ids: list[int],
        credits,
    ):
        starting = credits.pages(1000)
        await credits.set(balance_micros=starting)

        resp = await upload_file(
            client, headers, "empty.pdf", workspace_id=workspace_id
        )
        assert resp.status_code == 200
        doc_ids = resp.json()["document_ids"]
        cleanup_doc_ids.extend(doc_ids)

        if doc_ids:
            statuses = await poll_document_status(
                client, headers, doc_ids, workspace_id=workspace_id, timeout=120.0
            )
            for did in doc_ids:
                assert statuses[did]["status"]["state"] == "failed"

        balance = await _get_balance(client, headers)
        assert balance == starting, (
            f"balance should remain {starting} after ETL failure, got {balance}"
        )


# ---------------------------------------------------------------------------
# Test F: Second upload rejected after first consumes remaining credit
# ---------------------------------------------------------------------------


class TestSecondUploadExceedsCredit:
    """Upload one PDF successfully, consuming the credit, then verify a second
    upload is rejected."""

    async def test_second_upload_rejected_after_credit_consumed(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        workspace_id: int,
        cleanup_doc_ids: list[int],
        credits,
    ):
        # Exactly one page of credit: the first 1-page PDF fits, the second
        # is rejected once the wallet hits zero.
        await credits.set(balance_micros=credits.pages(1))

        resp1 = await upload_file(
            client, headers, "sample.pdf", workspace_id=workspace_id
        )
        assert resp1.status_code == 200
        first_ids = resp1.json()["document_ids"]
        cleanup_doc_ids.extend(first_ids)

        statuses1 = await poll_document_status(
            client, headers, first_ids, workspace_id=workspace_id, timeout=300.0
        )
        for did in first_ids:
            assert statuses1[did]["status"]["state"] == "ready"

        resp2 = await upload_file(
            client,
            headers,
            "sample.pdf",
            workspace_id=workspace_id,
            filename_override="sample_copy.pdf",
        )
        assert resp2.status_code == 200
        second_ids = resp2.json()["document_ids"]
        cleanup_doc_ids.extend(second_ids)

        statuses2 = await poll_document_status(
            client, headers, second_ids, workspace_id=workspace_id, timeout=300.0
        )
        for did in second_ids:
            assert statuses2[did]["status"]["state"] == "failed"
            reason = statuses2[did]["status"].get("reason", "").lower()
            assert "credit" in reason, (
                f"Expected 'credit' in failure reason, got: {reason!r}"
            )
