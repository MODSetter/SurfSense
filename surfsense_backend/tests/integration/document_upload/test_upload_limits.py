"""
Integration tests for backend file upload limit enforcement.

These tests verify that the API rejects uploads that exceed the per-file
size cap. The cap is configurable via MAX_FILE_SIZE_MB (default 500 MB),
so tests derive their sizes from the value the app actually resolved at
import time rather than hardcoding it — otherwise this suite fails for
anyone who has MAX_FILE_SIZE_MB set in their environment.

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

from app.routes.documents_routes import MAX_FILE_SIZE_BYTES

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Test: Per-file size limit
# ---------------------------------------------------------------------------


class TestPerFileSizeLimit:
    """A single file exceeding MAX_FILE_SIZE_BYTES should be rejected."""

    async def test_oversized_file_returns_413(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        workspace_id: int,
    ):
        oversized = io.BytesIO(b"\x00" * (MAX_FILE_SIZE_BYTES + 1))
        resp = await client.post(
            "/api/v1/documents/fileupload",
            headers=headers,
            files=[("files", ("big.pdf", oversized, "application/pdf"))],
            data={"workspace_id": str(workspace_id)},
        )
        assert resp.status_code == 413
        assert "per-file limit" in resp.json()["detail"].lower()

    async def test_file_at_limit_accepted(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        workspace_id: int,
        cleanup_doc_ids: list[int],
    ):
        at_limit = io.BytesIO(b"\x00" * MAX_FILE_SIZE_BYTES)
        resp = await client.post(
            "/api/v1/documents/fileupload",
            headers=headers,
            files=[("files", ("exactlimit.txt", at_limit, "text/plain"))],
            data={"workspace_id": str(workspace_id)},
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
        workspace_id: int,
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
            data={"workspace_id": str(workspace_id)},
        )
        assert resp.status_code == 200
        cleanup_doc_ids.extend(resp.json().get("document_ids", []))
