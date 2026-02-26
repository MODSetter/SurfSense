"""
Integration tests for backend file upload limit enforcement.

These tests verify that the API rejects uploads that exceed:
  - Max files per upload (10)
  - Max per-file size (50 MB)
  - Max total upload size (200 MB)

The limits mirror the frontend's DocumentUploadTab.tsx constants and are
enforced server-side to protect against direct API calls.

Prerequisites:
  - PostgreSQL + pgvector
"""

from __future__ import annotations

import io

import httpx
import pytest

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Test A: File count limit
# ---------------------------------------------------------------------------


class TestFileCountLimit:
    """Uploading more than 10 files in a single request should be rejected."""

    async def test_11_files_returns_413(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        search_space_id: int,
    ):
        files = [
            ("files", (f"file_{i}.txt", io.BytesIO(b"test content"), "text/plain"))
            for i in range(11)
        ]
        resp = await client.post(
            "/api/v1/documents/fileupload",
            headers=headers,
            files=files,
            data={"search_space_id": str(search_space_id)},
        )
        assert resp.status_code == 413
        assert "too many files" in resp.json()["detail"].lower()

    async def test_10_files_accepted(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        search_space_id: int,
        cleanup_doc_ids: list[int],
    ):
        files = [
            ("files", (f"file_{i}.txt", io.BytesIO(b"test content"), "text/plain"))
            for i in range(10)
        ]
        resp = await client.post(
            "/api/v1/documents/fileupload",
            headers=headers,
            files=files,
            data={"search_space_id": str(search_space_id)},
        )
        assert resp.status_code == 200
        cleanup_doc_ids.extend(resp.json().get("document_ids", []))


# ---------------------------------------------------------------------------
# Test B: Per-file size limit
# ---------------------------------------------------------------------------


class TestPerFileSizeLimit:
    """A single file exceeding 50 MB should be rejected."""

    async def test_oversized_file_returns_413(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        search_space_id: int,
    ):
        oversized = io.BytesIO(b"\x00" * (50 * 1024 * 1024 + 1))
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
        at_limit = io.BytesIO(b"\x00" * (50 * 1024 * 1024))
        resp = await client.post(
            "/api/v1/documents/fileupload",
            headers=headers,
            files=[("files", ("exact50mb.txt", at_limit, "text/plain"))],
            data={"search_space_id": str(search_space_id)},
        )
        assert resp.status_code == 200
        cleanup_doc_ids.extend(resp.json().get("document_ids", []))


# ---------------------------------------------------------------------------
# Test C: Total upload size limit
# ---------------------------------------------------------------------------


class TestTotalSizeLimit:
    """Multiple files whose combined size exceeds 200 MB should be rejected."""

    async def test_total_size_over_200mb_returns_413(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        search_space_id: int,
    ):
        chunk_size = 45 * 1024 * 1024  # 45 MB each
        files = [
            (
                "files",
                (f"chunk_{i}.txt", io.BytesIO(b"\x00" * chunk_size), "text/plain"),
            )
            for i in range(5)  # 5 x 45 MB = 225 MB > 200 MB
        ]
        resp = await client.post(
            "/api/v1/documents/fileupload",
            headers=headers,
            files=files,
            data={"search_space_id": str(search_space_id)},
        )
        assert resp.status_code == 413
        assert "total upload size" in resp.json()["detail"].lower()
