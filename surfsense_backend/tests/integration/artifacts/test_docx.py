from __future__ import annotations

import json
import time
from contextlib import asynccontextmanager
from io import BytesIO
from unittest.mock import AsyncMock
from zipfile import ZipFile

import pytest
from langchain.tools import ToolRuntime
from sqlalchemy import func, select

from app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.tools import (
    load_artifact_source as load_source_tool,
    save_artifact as save_artifact_tool,
)
from app.artifacts import service
from app.artifacts.verification.receipt import (
    VerificationReceipt,
    sha256_bytes,
    write_receipt,
)
from app.db import Document
from app.file_storage.persistence.models import DocumentFile
from app.file_storage.service import purge_document_blobs
from app.routes import editor_routes
from tests.utils.fake_sandbox import FakeSandboxSession

from .test_service import MemoryBackend

pytestmark = pytest.mark.integration
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
SECRET = "test-secret"


def _docx_bytes(label: str) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("_rels/.rels", "<Relationships/>")
        archive.writestr("word/document.xml", f"<document>{label}</document>")
    return output.getvalue()


def _runtime() -> ToolRuntime:
    return ToolRuntime(
        state={},
        context=None,
        config={"configurable": {"thread_id": "77::task:docx"}},
        stream_writer=None,
        tool_call_id="docx",
        store=None,
    )


async def _verify(sandbox: FakeSandboxSession, workspace_id: int) -> None:
    await write_receipt(
        sandbox,
        VerificationReceipt(
            workspace_id=workspace_id,
            session_id=sandbox.session_id,
            format="docx",
            primary_path="/workspace/report.docx",
            primary_sha256=sha256_bytes(sandbox.files["/workspace/report.docx"]),
            preview_path="/tmp/report.pdf",
            preview_sha256=sha256_bytes(sandbox.files["/tmp/report.pdf"]),
            page_count=1,
            visual="clean",
            issued_at=int(time.time()),
        ),
        SECRET,
    )


async def test_docx_tool_create_revise_editor_contract_and_purge(
    db_session, db_workspace, monkeypatch
):
    backend = MemoryBackend()
    sandbox = FakeSandboxSession(
        {
            "/workspace/report.docx": _docx_bytes("first"),
            "/workspace/report.js": b"const version = 1",
            "/tmp/report.pdf": b"%PDF-preview",
        }
    )
    await _verify(sandbox, db_workspace.id)

    class Registry:
        async def get_session(self, _thread_id, _workspace_id):
            return sandbox

    async def get_registry():
        return Registry()

    @asynccontextmanager
    async def session_context():
        yield db_session

    monkeypatch.setattr(service, "get_storage_backend", lambda *_: backend)
    monkeypatch.setattr(
        service, "knowledge_store_enabled_for", AsyncMock(return_value=False)
    )
    monkeypatch.setattr(service, "_index_legacy", AsyncMock())
    monkeypatch.setattr(save_artifact_tool, "get_registry", get_registry)
    monkeypatch.setattr(save_artifact_tool, "shielded_async_session", session_context)
    monkeypatch.setattr(save_artifact_tool.app_config, "SECRET_KEY", SECRET)
    monkeypatch.setattr(load_source_tool, "get_registry", get_registry)
    monkeypatch.setattr(load_source_tool, "shielded_async_session", session_context)
    monkeypatch.setattr(load_source_tool, "get_storage_backend", lambda *_: backend)
    monkeypatch.setattr(editor_routes, "check_permission", AsyncMock())
    tool = save_artifact_tool.create_save_artifact_tool(db_workspace.id)

    sandbox.files["/workspace/report.docx"] = _docx_bytes("changed-before-save")
    rejected = await tool.coroutine(
        title="Report",
        markdown_representation="# Report\n\nFirst version",
        path="/workspace/report.docx",
        source_path="/workspace/report.js",
        preview_path="/tmp/report.pdf",
        runtime=_runtime(),
    )
    assert "changed after verification" in str(rejected)

    await _verify(sandbox, db_workspace.id)
    created_command = await tool.coroutine(
        title="Report",
        markdown_representation="# Report\n\nFirst version",
        path="/workspace/report.docx",
        source_path="/workspace/report.js",
        preview_path="/tmp/report.pdf",
        runtime=_runtime(),
    )
    created = json.loads(created_command.update["messages"][0].content)
    document_id = created["document_id"]

    assert [(file["role"], file["mime_type"]) for file in created["files"]] == [
        ("primary", DOCX_MIME),
        ("preview", "application/pdf"),
    ]
    response = await editor_routes.get_editor_content(
        db_workspace.id, document_id, db_session, object()
    )
    assert [file["role"] for file in response["files"]] == ["primary", "preview"]

    load_tool = load_source_tool.create_load_artifact_source_tool(
        workspace_id=db_workspace.id
    )
    loaded_path = await load_tool.coroutine(document_id=document_id, runtime=_runtime())
    assert loaded_path == f"/workspace/artifact-{document_id}-report.js"
    assert sandbox.files[loaded_path] == b"const version = 1"

    sandbox.files["/workspace/report.docx"] = _docx_bytes("second")
    sandbox.files["/workspace/report.js"] = (
        sandbox.files[loaded_path] + b"\nconst version = 2"
    )
    sandbox.files["/tmp/report.pdf"] = b"%PDF-preview-2"
    await _verify(sandbox, db_workspace.id)
    revised_command = await tool.coroutine(
        title="Report",
        markdown_representation="# Report\n\nSecond version",
        path="/workspace/report.docx",
        source_path="/workspace/report.js",
        preview_path="/tmp/report.pdf",
        document_id=document_id,
        runtime=_runtime(),
    )
    revised = json.loads(revised_command.update["messages"][0].content)

    assert revised["document_id"] == document_id
    assert (
        await db_session.scalar(
            select(func.count(Document.id)).where(Document.id == document_id)
        )
        == 1
    )
    assert (
        await db_session.scalar(
            select(func.count(DocumentFile.id)).where(
                DocumentFile.document_id == document_id
            )
        )
        == 3
    )
    stored_source = await db_session.scalar(
        select(DocumentFile).where(
            DocumentFile.document_id == document_id,
            DocumentFile.role == "source",
        )
    )
    assert stored_source.original_filename == "report.js"

    await purge_document_blobs(
        db_session,
        document_ids=[document_id],
        backend=backend,
    )
    assert backend.data == {}
