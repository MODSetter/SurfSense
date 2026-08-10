from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select

from app.artifacts import service
from app.artifacts.service import ArtifactFileInput, save_artifact
from app.db import Document, DocumentRevision, DocumentVersion
from app.file_storage.backends.base import StorageBackend
from app.file_storage.persistence.models import DocumentFile

pytestmark = pytest.mark.integration


class MemoryBackend(StorageBackend):
    backend_name = "memory"

    def __init__(self, *, fail_on_put: int | None = None) -> None:
        self.data: dict[str, bytes] = {}
        self.puts = 0
        self.fail_on_put = fail_on_put

    async def put(self, key: str, data: bytes, *, content_type: str | None = None):
        del content_type
        self.puts += 1
        if self.fail_on_put == self.puts:
            raise RuntimeError("forced storage failure")
        self.data[key] = data

    async def delete(self, key: str):
        self.data.pop(key, None)

    async def exists(self, key: str) -> bool:
        return key in self.data

    async def _stream(self, key: str):
        yield self.data[key]

    def open_stream(self, key: str):
        return self._stream(key)


@pytest.fixture
def artifact_setup(monkeypatch):
    backend = MemoryBackend()
    monkeypatch.setattr(service, "get_storage_backend", lambda *_: backend)
    monkeypatch.setattr(
        service, "knowledge_store_enabled_for", AsyncMock(return_value=False)
    )
    monkeypatch.setattr(service, "_index_legacy", AsyncMock())
    return backend


async def test_markdown_artifact_payload_and_fences(
    db_session, db_workspace, artifact_setup
):
    saved = await save_artifact(
        db_session,
        workspace_id=db_workspace.id,
        thread_id=10,
        tool_call_id="call-1",
        title="Project brief",
        markdown_representation="# Project brief\n\nBody",
        files=[],
    )

    assert saved.status == "saved"
    assert saved.title == "Project brief"
    assert saved.files == []
    document = await db_session.get(Document, saved.document_id)
    assert document.document_metadata == {
        "generated": True,
        "thread_id": 10,
        "tool_call_id": "call-1",
    }
    assert document.path == "/documents/Project brief.md"
    assert (
        await db_session.scalar(
            select(func.count(DocumentVersion.id)).where(
                DocumentVersion.document_id == saved.document_id
            )
        )
        == 0
    )
    assert (
        await db_session.scalar(
            select(func.count(DocumentRevision.id)).where(
                DocumentRevision.document_id == saved.document_id
            )
        )
        == 0
    )


async def test_binary_create_and_revision_replace_files(
    db_session, db_workspace, artifact_setup
):
    backend = artifact_setup
    created = await save_artifact(
        db_session,
        workspace_id=db_workspace.id,
        thread_id=10,
        tool_call_id="call-1",
        title="Seeded PDF",
        markdown_representation="# Seeded PDF",
        files=[
            ArtifactFileInput(
                data=b"old-pdf",
                filename="seeded.pdf",
                mime_type="application/pdf",
            ),
            ArtifactFileInput(
                data=b"old source",
                filename="seeded.py",
                mime_type="text/x-python",
                role="source",
            ),
        ],
        extra_metadata={"verification": {"verified": True, "reason": None}},
    )
    old_rows = (
        await db_session.scalars(
            select(DocumentFile).where(DocumentFile.document_id == created.document_id)
        )
    ).all()
    old_primary = next(row for row in old_rows if row.role == "primary")
    old_keys = {row.storage_key for row in old_rows}

    revised = await save_artifact(
        db_session,
        workspace_id=db_workspace.id,
        thread_id=10,
        tool_call_id="call-2",
        title="Retitled PDF",
        markdown_representation="# Retitled",
        document_id=created.document_id,
        files=[
            ArtifactFileInput(
                data=b"new-pdf",
                filename="retitled.pdf",
                mime_type="application/pdf",
            ),
            ArtifactFileInput(
                data=b"new source",
                filename="retitled.py",
                mime_type="text/x-python",
                role="source",
            ),
        ],
        extra_metadata={
            "verification": {
                "verified": False,
                "reason": "No vision model configured",
            }
        },
    )

    assert revised.document_id == created.document_id
    assert [file.role for file in revised.files] == ["primary"]
    assert revised.files[0].file_id != old_primary.id
    assert old_keys.isdisjoint(backend.data)
    rows = list(
        (
            await db_session.scalars(
                select(DocumentFile).where(
                    DocumentFile.document_id == created.document_id
                )
            )
        ).all()
    )
    assert {(row.role, row.original_filename) for row in rows} == {
        ("primary", "retitled.pdf"),
        ("source", "retitled.py"),
    }
    document = await db_session.get(Document, created.document_id)
    assert document.document_metadata["generated"] is True
    assert document.document_metadata["tool_call_id"] == "call-2"
    assert document.document_metadata["verification"] == {
        "verified": False,
        "reason": "No vision model configured",
    }


async def test_storage_failure_rolls_back_document_and_blob(
    db_session, db_workspace, monkeypatch
):
    backend = MemoryBackend(fail_on_put=2)
    monkeypatch.setattr(service, "get_storage_backend", lambda *_: backend)
    monkeypatch.setattr(
        service, "knowledge_store_enabled_for", AsyncMock(return_value=False)
    )
    monkeypatch.setattr(service, "_index_legacy", AsyncMock())

    with pytest.raises(RuntimeError, match="forced storage failure"):
        await save_artifact(
            db_session,
            workspace_id=db_workspace.id,
            thread_id=10,
            tool_call_id="call-fail",
            title="Must rollback",
            markdown_representation="# Rollback",
            files=[
                ArtifactFileInput(b"first", "first.pdf", "application/pdf"),
                ArtifactFileInput(
                    b"second", "preview.pdf", "application/pdf", "preview"
                ),
            ],
        )

    assert not backend.data
    assert (
        await db_session.scalar(
            select(func.count(Document.id)).where(Document.title == "Must rollback")
        )
        == 0
    )


async def test_failed_revision_keeps_previous_generation(
    db_session, db_workspace, artifact_setup, monkeypatch
):
    backend = artifact_setup
    created = await save_artifact(
        db_session,
        workspace_id=db_workspace.id,
        thread_id=10,
        tool_call_id="call-1",
        title="Stable",
        markdown_representation="# Stable",
        files=[ArtifactFileInput(b"stable", "stable.pdf", "application/pdf")],
    )
    previous_keys = set(backend.data)
    backend.fail_on_put = backend.puts + 2

    with pytest.raises(RuntimeError, match="forced storage failure"):
        await save_artifact(
            db_session,
            workspace_id=db_workspace.id,
            thread_id=10,
            tool_call_id="call-2",
            title="Broken revision",
            markdown_representation="# Broken",
            document_id=created.document_id,
            files=[
                ArtifactFileInput(b"new", "new.pdf", "application/pdf"),
                ArtifactFileInput(
                    b"preview", "preview.pdf", "application/pdf", "preview"
                ),
            ],
        )

    document = await db_session.get(Document, created.document_id)
    await db_session.refresh(document)
    assert document.title == "Stable"
    assert document.source_markdown == "# Stable"
    assert set(backend.data) == previous_keys
    rows = (
        await db_session.scalars(
            select(DocumentFile).where(DocumentFile.document_id == created.document_id)
        )
    ).all()
    assert [row.original_filename for row in rows] == ["stable.pdf"]
