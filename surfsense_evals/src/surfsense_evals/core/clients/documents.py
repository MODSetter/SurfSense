"""Client for ``/api/v1/documents/{fileupload,status,{id}/chunks}``.

Verified against:

* ``surfsense_backend/app/routes/documents_routes.py:122-292`` (POST fileupload)
* ``surfsense_backend/app/routes/documents_routes.py:806-871`` (GET status batch)
* ``surfsense_backend/app/routes/documents_routes.py:1062-1128`` (GET {id}/chunks paginated)

Document processing is asynchronous:
* ``POST /documents/fileupload`` returns immediately with
  ``document_ids`` in ``pending``;
* a Celery worker moves each through ``processing → ready/failed``;
* the harness polls ``GET /documents/status?document_ids=...`` until
  every doc is ``ready`` (otherwise the retriever sees an empty corpus
  and accuracy numbers are meaningless).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import mimetypes
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class FileUploadResult:
    """Mirrors the JSON returned by ``POST /documents/fileupload``."""

    document_ids: list[int]
    duplicate_document_ids: list[int]
    total_files: int
    pending_files: int
    skipped_duplicates: int
    message: str = ""

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> FileUploadResult:
        return cls(
            document_ids=[int(x) for x in payload.get("document_ids", [])],
            duplicate_document_ids=[int(x) for x in payload.get("duplicate_document_ids", [])],
            total_files=int(payload.get("total_files", 0)),
            pending_files=int(payload.get("pending_files", 0)),
            skipped_duplicates=int(payload.get("skipped_duplicates", 0)),
            message=str(payload.get("message", "")),
        )


@dataclass
class DocumentStatus:
    document_id: int
    title: str
    document_type: str
    state: str
    reason: str | None = None

    @property
    def is_ready(self) -> bool:
        return self.state == "ready"

    @property
    def is_failed(self) -> bool:
        return self.state == "failed"


@dataclass
class ChunkRow:
    id: int
    document_id: int
    content: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


class DocumentProcessingFailed(RuntimeError):
    """Raised when a polled document lands in ``failed``."""

    def __init__(self, statuses: Sequence[DocumentStatus]) -> None:
        details = ", ".join(
            f"id={s.document_id} ({s.title!r}): {s.reason or 'unknown'}" for s in statuses
        )
        super().__init__(f"Document(s) failed to process: {details}")
        self.statuses = list(statuses)


class DocumentProcessingTimeout(RuntimeError):
    """Raised when polling exceeds the per-doc timeout budget."""


class DocumentsClient:
    """Document upload + status polling + chunk listing."""

    def __init__(self, http: httpx.AsyncClient, base_url: str) -> None:
        self._http = http
        self._base = base_url.rstrip("/")

    # ------------------------------------------------------------------
    # upload
    # ------------------------------------------------------------------

    async def upload(
        self,
        files: Iterable[Path],
        *,
        search_space_id: int,
        use_vision_llm: bool = False,
        processing_mode: str = "basic",
    ) -> FileUploadResult:
        """Upload files to ``/api/v1/documents/fileupload``.

        ``files`` is materialised to a list because we may need to
        re-read on retry. Caller is responsible for ensuring each path
        exists and respects the per-file size cap (50 MB backend default).
        """

        materialised = [Path(p) for p in files]
        if not materialised:
            return FileUploadResult(
                document_ids=[],
                duplicate_document_ids=[],
                total_files=0,
                pending_files=0,
                skipped_duplicates=0,
                message="No files supplied",
            )

        opened: list[tuple[str, Any]] = []
        try:
            for path in materialised:
                # ``open`` directly — httpx wraps it in MultipartStream.
                file_obj = path.open("rb")
                mime, _ = mimetypes.guess_type(path.name)
                opened.append(
                    (
                        "files",
                        (path.name, file_obj, mime or "application/octet-stream"),
                    )
                )

            response = await self._http.post(
                f"{self._base}/api/v1/documents/fileupload",
                data={
                    "search_space_id": str(search_space_id),
                    "use_vision_llm": "true" if use_vision_llm else "false",
                    "processing_mode": processing_mode,
                },
                files=opened,
                # Multipart uploads can be slow for big PDFs; bump per-call.
                timeout=httpx.Timeout(120.0, connect=10.0),
            )
        finally:
            for _, (_, file_obj, _) in opened:
                with contextlib.suppress(Exception):
                    file_obj.close()

        response.raise_for_status()
        return FileUploadResult.from_payload(response.json())

    # ------------------------------------------------------------------
    # status polling
    # ------------------------------------------------------------------

    async def get_status(
        self, *, search_space_id: int, document_ids: Sequence[int]
    ) -> list[DocumentStatus]:
        if not document_ids:
            return []
        response = await self._http.get(
            f"{self._base}/api/v1/documents/status",
            params={
                "search_space_id": search_space_id,
                "document_ids": ",".join(str(d) for d in document_ids),
            },
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()
        return [
            DocumentStatus(
                document_id=int(item["id"]),
                title=str(item.get("title", "")),
                document_type=str(item.get("document_type", "")),
                state=str((item.get("status") or {}).get("state", "ready")),
                reason=(item.get("status") or {}).get("reason"),
            )
            for item in payload.get("items", [])
        ]

    async def wait_until_ready(
        self,
        *,
        search_space_id: int,
        document_ids: Sequence[int],
        timeout_s: float = 300.0,
        initial_poll_s: float = 1.0,
        max_poll_s: float = 10.0,
    ) -> list[DocumentStatus]:
        """Poll ``GET /documents/status`` until every doc is ``ready``.

        Exponential backoff from ``initial_poll_s`` up to ``max_poll_s``.
        Raises ``DocumentProcessingFailed`` if any doc lands in
        ``failed`` (with the offending document ids), or
        ``DocumentProcessingTimeout`` if the budget is exhausted.
        """

        if not document_ids:
            return []
        deadline = asyncio.get_event_loop().time() + timeout_s
        poll = initial_poll_s
        while True:
            statuses = await self.get_status(
                search_space_id=search_space_id, document_ids=document_ids
            )
            failed = [s for s in statuses if s.is_failed]
            if failed:
                raise DocumentProcessingFailed(failed)
            ready = [s for s in statuses if s.is_ready]
            if len(ready) == len(document_ids):
                return statuses
            now = asyncio.get_event_loop().time()
            if now >= deadline:
                pending = [s for s in statuses if not s.is_ready and not s.is_failed]
                pending_ids = [s.document_id for s in pending]
                raise DocumentProcessingTimeout(
                    f"Timed out after {timeout_s:.0f}s waiting for documents "
                    f"(still pending/processing: {pending_ids})"
                )
            await asyncio.sleep(min(poll, max(0.1, deadline - now)))
            poll = min(poll * 1.5, max_poll_s)

    # ------------------------------------------------------------------
    # chunks (chunk_id -> document_id map)
    # ------------------------------------------------------------------

    async def list_chunks(self, document_id: int, *, page_size: int = 100) -> list[ChunkRow]:
        """Walk ``GET /documents/{id}/chunks`` until ``has_more=False``.

        Used by ingestion to materialise the ``chunk_id -> document_id``
        map needed for retrieval scoring (CUREv1).
        """

        rows: list[ChunkRow] = []
        page = 0
        while True:
            response = await self._http.get(
                f"{self._base}/api/v1/documents/{document_id}/chunks",
                params={"page": page, "page_size": page_size},
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()
            for item in payload.get("items", []):
                rows.append(
                    ChunkRow(
                        id=int(item["id"]),
                        document_id=document_id,
                        content=str(item.get("content", "")),
                        raw=item,
                    )
                )
            if not payload.get("has_more"):
                break
            page += 1
        return rows
