"""
End-to-end tests for manual document upload.

These tests exercise the full pipeline:
  API upload → Celery task → ETL extraction → chunking → embedding → DB storage

Prerequisites (must be running):
  - FastAPI backend
  - PostgreSQL + pgvector
  - Redis
  - Celery worker
"""

from __future__ import annotations

import shutil
from pathlib import Path

import httpx
import pytest

from tests.utils.helpers import (
    FIXTURES_DIR,
    delete_document,
    get_document,
    poll_document_status,
    upload_file,
    upload_multiple_files,
)

pytestmark = pytest.mark.e2e

# ---------------------------------------------------------------------------
# Helpers local to this module
# ---------------------------------------------------------------------------


def _assert_document_ready(doc: dict, *, expected_filename: str) -> None:
    """Common assertions for a successfully processed document."""
    assert doc["title"] == expected_filename
    assert doc["document_type"] == "FILE"
    assert doc["content"], "Document content (summary) should not be empty"
    assert doc["content_hash"], "content_hash should be set"
    assert doc["document_metadata"].get("FILE_NAME") == expected_filename


# ---------------------------------------------------------------------------
# Test A: Upload a .txt file (direct read path — no ETL service needed)
# ---------------------------------------------------------------------------


class TestTxtFileUpload:
    """Upload a plain-text file and verify the full pipeline."""

    async def test_upload_txt_returns_document_id(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        search_space_id: int,
        cleanup_doc_ids: list[int],
    ):
        resp = await upload_file(
            client, headers, "sample.txt", search_space_id=search_space_id
        )
        assert resp.status_code == 200

        body = resp.json()
        assert body["pending_files"] >= 1
        assert len(body["document_ids"]) >= 1
        cleanup_doc_ids.extend(body["document_ids"])

    async def test_txt_processing_reaches_ready(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        search_space_id: int,
        cleanup_doc_ids: list[int],
    ):
        resp = await upload_file(
            client, headers, "sample.txt", search_space_id=search_space_id
        )
        assert resp.status_code == 200
        doc_ids = resp.json()["document_ids"]
        cleanup_doc_ids.extend(doc_ids)

        statuses = await poll_document_status(
            client, headers, doc_ids, search_space_id=search_space_id
        )
        for did in doc_ids:
            assert statuses[did]["status"]["state"] == "ready"

    async def test_txt_document_fields_populated(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        search_space_id: int,
        cleanup_doc_ids: list[int],
    ):
        resp = await upload_file(
            client, headers, "sample.txt", search_space_id=search_space_id
        )
        doc_ids = resp.json()["document_ids"]
        cleanup_doc_ids.extend(doc_ids)

        await poll_document_status(
            client, headers, doc_ids, search_space_id=search_space_id
        )

        doc = await get_document(client, headers, doc_ids[0])
        _assert_document_ready(doc, expected_filename="sample.txt")
        assert doc["document_metadata"]["ETL_SERVICE"] == "MARKDOWN"


# ---------------------------------------------------------------------------
# Test B: Upload a .md file (markdown direct-read path)
# ---------------------------------------------------------------------------


class TestMarkdownFileUpload:
    """Upload a Markdown file and verify the full pipeline."""

    async def test_md_processing_reaches_ready(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        search_space_id: int,
        cleanup_doc_ids: list[int],
    ):
        resp = await upload_file(
            client, headers, "sample.md", search_space_id=search_space_id
        )
        assert resp.status_code == 200
        doc_ids = resp.json()["document_ids"]
        cleanup_doc_ids.extend(doc_ids)

        statuses = await poll_document_status(
            client, headers, doc_ids, search_space_id=search_space_id
        )
        for did in doc_ids:
            assert statuses[did]["status"]["state"] == "ready"

    async def test_md_document_fields_populated(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        search_space_id: int,
        cleanup_doc_ids: list[int],
    ):
        resp = await upload_file(
            client, headers, "sample.md", search_space_id=search_space_id
        )
        doc_ids = resp.json()["document_ids"]
        cleanup_doc_ids.extend(doc_ids)

        await poll_document_status(
            client, headers, doc_ids, search_space_id=search_space_id
        )

        doc = await get_document(client, headers, doc_ids[0])
        _assert_document_ready(doc, expected_filename="sample.md")
        assert doc["document_metadata"]["ETL_SERVICE"] == "MARKDOWN"


# ---------------------------------------------------------------------------
# Test C: Upload a .pdf file (ETL path — Docling / Unstructured)
# ---------------------------------------------------------------------------


class TestPdfFileUpload:
    """Upload a PDF and verify it goes through the ETL extraction pipeline."""

    async def test_pdf_processing_reaches_ready(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        search_space_id: int,
        cleanup_doc_ids: list[int],
    ):
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

    async def test_pdf_document_fields_populated(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        search_space_id: int,
        cleanup_doc_ids: list[int],
    ):
        resp = await upload_file(
            client, headers, "sample.pdf", search_space_id=search_space_id
        )
        doc_ids = resp.json()["document_ids"]
        cleanup_doc_ids.extend(doc_ids)

        await poll_document_status(
            client, headers, doc_ids, search_space_id=search_space_id, timeout=300.0
        )

        doc = await get_document(client, headers, doc_ids[0])
        _assert_document_ready(doc, expected_filename="sample.pdf")
        assert doc["document_metadata"]["ETL_SERVICE"] in {
            "DOCLING",
            "UNSTRUCTURED",
            "LLAMACLOUD",
        }


# ---------------------------------------------------------------------------
# Test D: Upload multiple files in a single request
# ---------------------------------------------------------------------------


class TestMultiFileUpload:
    """Upload several files at once and verify all are processed."""

    async def test_multi_upload_returns_all_ids(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        search_space_id: int,
        cleanup_doc_ids: list[int],
    ):
        resp = await upload_multiple_files(
            client,
            headers,
            ["sample.txt", "sample.md"],
            search_space_id=search_space_id,
        )
        assert resp.status_code == 200

        body = resp.json()
        assert body["pending_files"] == 2
        assert len(body["document_ids"]) == 2
        cleanup_doc_ids.extend(body["document_ids"])

    async def test_multi_upload_all_reach_ready(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        search_space_id: int,
        cleanup_doc_ids: list[int],
    ):
        resp = await upload_multiple_files(
            client,
            headers,
            ["sample.txt", "sample.md"],
            search_space_id=search_space_id,
        )
        doc_ids = resp.json()["document_ids"]
        cleanup_doc_ids.extend(doc_ids)

        statuses = await poll_document_status(
            client, headers, doc_ids, search_space_id=search_space_id
        )
        for did in doc_ids:
            assert statuses[did]["status"]["state"] == "ready"


# ---------------------------------------------------------------------------
# Test E: Duplicate file upload (same file uploaded twice)
# ---------------------------------------------------------------------------


class TestDuplicateFileUpload:
    """
    Uploading the exact same file a second time should be detected as a
    duplicate via ``unique_identifier_hash``.
    """

    async def test_duplicate_file_is_skipped(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        search_space_id: int,
        cleanup_doc_ids: list[int],
    ):
        # First upload
        resp1 = await upload_file(
            client, headers, "sample.txt", search_space_id=search_space_id
        )
        assert resp1.status_code == 200
        first_ids = resp1.json()["document_ids"]
        cleanup_doc_ids.extend(first_ids)

        await poll_document_status(
            client, headers, first_ids, search_space_id=search_space_id
        )

        # Second upload of the same file
        resp2 = await upload_file(
            client, headers, "sample.txt", search_space_id=search_space_id
        )
        assert resp2.status_code == 200

        body2 = resp2.json()
        assert body2["skipped_duplicates"] >= 1
        assert len(body2["duplicate_document_ids"]) >= 1
        cleanup_doc_ids.extend(body2.get("document_ids", []))


# ---------------------------------------------------------------------------
# Test F: Duplicate content detection (different name, same content)
# ---------------------------------------------------------------------------


class TestDuplicateContentDetection:
    """
    Uploading a file with a different name but identical content should be
    detected as duplicate content via ``content_hash``.
    """

    async def test_same_content_different_name_detected(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        search_space_id: int,
        cleanup_doc_ids: list[int],
        tmp_path: Path,
    ):
        # First upload
        resp1 = await upload_file(
            client, headers, "sample.txt", search_space_id=search_space_id
        )
        assert resp1.status_code == 200
        first_ids = resp1.json()["document_ids"]
        cleanup_doc_ids.extend(first_ids)
        await poll_document_status(
            client, headers, first_ids, search_space_id=search_space_id
        )

        # Copy fixture content to a differently named temp file
        src = FIXTURES_DIR / "sample.txt"
        dest = tmp_path / "renamed_sample.txt"
        shutil.copy2(src, dest)

        with open(dest, "rb") as f:
            resp2 = await client.post(
                "/api/v1/documents/fileupload",
                headers=headers,
                files={"files": ("renamed_sample.txt", f)},
                data={"search_space_id": str(search_space_id)},
            )
        assert resp2.status_code == 200
        second_ids = resp2.json()["document_ids"]
        cleanup_doc_ids.extend(second_ids)
        assert second_ids, (
            "Expected at least one document id for renamed duplicate content upload"
        )

        statuses = await poll_document_status(
            client, headers, second_ids, search_space_id=search_space_id
        )
        for did in second_ids:
            assert statuses[did]["status"]["state"] == "failed"
            assert "duplicate" in statuses[did]["status"].get("reason", "").lower()


# ---------------------------------------------------------------------------
# Test G: Empty / corrupt file handling
# ---------------------------------------------------------------------------


class TestEmptyFileUpload:
    """An empty file should be processed but ultimately fail gracefully."""

    async def test_empty_pdf_fails(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        search_space_id: int,
        cleanup_doc_ids: list[int],
    ):
        resp = await upload_file(
            client, headers, "empty.pdf", search_space_id=search_space_id
        )
        assert resp.status_code == 200

        doc_ids = resp.json()["document_ids"]
        cleanup_doc_ids.extend(doc_ids)
        assert doc_ids, "Expected at least one document id for empty PDF upload"

        statuses = await poll_document_status(
            client, headers, doc_ids, search_space_id=search_space_id, timeout=120.0
        )
        for did in doc_ids:
            assert statuses[did]["status"]["state"] == "failed"
            assert statuses[did]["status"].get("reason"), (
                "Failed document should include a reason"
            )


# ---------------------------------------------------------------------------
# Test H: Upload without authentication
# ---------------------------------------------------------------------------


class TestUnauthenticatedUpload:
    """Requests without a valid JWT should be rejected."""

    async def test_upload_without_auth_returns_401(
        self,
        client: httpx.AsyncClient,
        search_space_id: int,
    ):
        file_path = FIXTURES_DIR / "sample.txt"
        with open(file_path, "rb") as f:
            resp = await client.post(
                "/api/v1/documents/fileupload",
                files={"files": ("sample.txt", f)},
                data={"search_space_id": str(search_space_id)},
            )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Test I: Upload with no files attached
# ---------------------------------------------------------------------------


class TestNoFilesUpload:
    """Submitting the form with zero files should return a validation error."""

    async def test_no_files_returns_error(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        search_space_id: int,
    ):
        resp = await client.post(
            "/api/v1/documents/fileupload",
            headers=headers,
            data={"search_space_id": str(search_space_id)},
        )
        assert resp.status_code in {400, 422}


# ---------------------------------------------------------------------------
# Test J: Document deletion after successful upload
# ---------------------------------------------------------------------------


class TestDocumentDeletion:
    """Upload, wait for ready, delete, then verify it's gone."""

    async def test_delete_processed_document(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        search_space_id: int,
    ):
        resp = await upload_file(
            client, headers, "sample.txt", search_space_id=search_space_id
        )
        doc_ids = resp.json()["document_ids"]
        await poll_document_status(
            client, headers, doc_ids, search_space_id=search_space_id
        )

        del_resp = await delete_document(client, headers, doc_ids[0])
        assert del_resp.status_code == 200

        get_resp = await client.get(
            f"/api/v1/documents/{doc_ids[0]}",
            headers=headers,
        )
        assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# Test K: Cannot delete a document while it is still processing
# ---------------------------------------------------------------------------


class TestDeleteWhileProcessing:
    """Attempting to delete a pending/processing document should be rejected."""

    async def test_delete_pending_document_returns_409(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        search_space_id: int,
        cleanup_doc_ids: list[int],
    ):
        resp = await upload_file(
            client, headers, "sample.pdf", search_space_id=search_space_id
        )
        assert resp.status_code == 200
        doc_ids = resp.json()["document_ids"]
        cleanup_doc_ids.extend(doc_ids)

        # Immediately try to delete before processing finishes
        del_resp = await delete_document(client, headers, doc_ids[0])
        assert del_resp.status_code == 409

        # Let it finish so cleanup can work
        await poll_document_status(
            client, headers, doc_ids, search_space_id=search_space_id, timeout=300.0
        )


# ---------------------------------------------------------------------------
# Test L: Status polling returns correct structure
# ---------------------------------------------------------------------------


class TestDocumentSearchability:
    """After upload reaches ready, the document must appear in the title search."""

    async def test_uploaded_document_appears_in_search(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        search_space_id: int,
        cleanup_doc_ids: list[int],
    ):
        resp = await upload_file(
            client, headers, "sample.txt", search_space_id=search_space_id
        )
        assert resp.status_code == 200
        doc_ids = resp.json()["document_ids"]
        cleanup_doc_ids.extend(doc_ids)

        await poll_document_status(
            client, headers, doc_ids, search_space_id=search_space_id
        )

        search_resp = await client.get(
            "/api/v1/documents/search",
            headers=headers,
            params={"title": "sample", "search_space_id": search_space_id},
        )
        assert search_resp.status_code == 200

        result_ids = [d["id"] for d in search_resp.json()["items"]]
        assert doc_ids[0] in result_ids, (
            f"Uploaded document {doc_ids[0]} not found in search results: {result_ids}"
        )


class TestStatusPolling:
    """Verify the status endpoint returns well-formed responses."""

    async def test_status_endpoint_returns_items(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        search_space_id: int,
        cleanup_doc_ids: list[int],
    ):
        resp = await upload_file(
            client, headers, "sample.txt", search_space_id=search_space_id
        )
        doc_ids = resp.json()["document_ids"]
        cleanup_doc_ids.extend(doc_ids)

        status_resp = await client.get(
            "/api/v1/documents/status",
            headers=headers,
            params={
                "search_space_id": search_space_id,
                "document_ids": ",".join(str(d) for d in doc_ids),
            },
        )
        assert status_resp.status_code == 200

        body = status_resp.json()
        assert "items" in body
        assert len(body["items"]) == len(doc_ids)
        for item in body["items"]:
            assert "id" in item
            assert "status" in item
            assert "state" in item["status"]
            assert item["status"]["state"] in {
                "pending",
                "processing",
                "ready",
                "failed",
            }

        await poll_document_status(
            client, headers, doc_ids, search_space_id=search_space_id
        )
