"""
Integration tests for backend file upload limit enforcement.

These tests verify that the API rejects uploads that exceed:
  - Max per-file size (500 MB)

No file count or total size limits are enforced — the frontend batches
uploads in groups of 5 and there is no cap on how many files a user can
upload in a single session.

Prerequisites:
  - PostgreSQL + pgvector
"""

from __future__ import annotations

import io

import httpx
import pytest

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Test: Per-file size limit (500 MB)
# ---------------------------------------------------------------------------


class TestPerFileSizeLimit:
    """A single file exceeding 500 MB should be rejected."""

    async def test_oversized_file_returns_413(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        search_space_id: int,
    ):
        oversized = io.BytesIO(b"\x00" * (500 * 1024 * 1024 + 1))
        resp = await client.post(
            "/api/v1/documents/fileupload",
            headers=headers,
            files=[("files", ("big.pdf", oversized, "application/pdf"))],
            data={"search_space_id": str(search_space_id)},
        )
        assert resp.status_code == 413
        assert "per-file limit" in resp.json()["detail"].lower()

    async def test_file_at_limit_accepted(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        search_space_id: int,
        cleanup_doc_ids: list[int],
    ):
        at_limit = io.BytesIO(b"\x00" * (500 * 1024 * 1024))
        resp = await client.post(
            "/api/v1/documents/fileupload",
            headers=headers,
            files=[("files", ("exact500mb.txt", at_limit, "text/plain"))],
            data={"search_space_id": str(search_space_id)},
        )
        assert resp.status_code == 200
        cleanup_doc_ids.extend(resp.json().get("document_ids", []))


# ---------------------------------------------------------------------------
# Test: Multiple files accepted without count limit
# ---------------------------------------------------------------------------


class TestNoFileCountLimit:
    """Many files in a single request should be accepted."""

    async def test_many_files_accepted(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        search_space_id: int,
        cleanup_doc_ids: list[int],
    ):
        files = [
            ("files", (f"file_{i}.txt", io.BytesIO(b"test content"), "text/plain"))
            for i in range(20)
        ]
        resp = await client.post(
            "/api/v1/documents/fileupload",
            headers=headers,
            files=files,
            data={"search_space_id": str(search_space_id)},
        )
        assert resp.status_code == 200
        cleanup_doc_ids.extend(resp.json().get("document_ids", []))
