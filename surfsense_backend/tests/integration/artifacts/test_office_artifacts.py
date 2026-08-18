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
    load_artifact_for_revision as load_revision_tool,
    save_artifact as save_artifact_tool,
)
from app.artifacts import service
from app.artifacts.persistence import Artifact, ArtifactFile, ArtifactFileRole
from app.artifacts.verification.formats.registry import DOCX_MIME, PPTX_MIME
from app.artifacts.verification.receipt import (
    VerificationReceipt,
    sha256_bytes,
    write_receipt,
)
from app.db import Chunk, Document
from app.file_storage.service import purge_document_blobs
from tests.utils.fake_sandbox import FakeSandboxSession

from .test_service import MemoryBackend

pytestmark = pytest.mark.integration
SECRET = "test-secret"


def _office_bytes(format_name: str, label: str) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("_rels/.rels", "<Relationships/>")
        if format_name == "docx":
            archive.writestr("word/document.xml", f"<document>{label}</document>")
        else:
            archive.writestr(
                "ppt/presentation.xml", f"<presentation>{label}</presentation>"
            )
    return output.getvalue()


def _runtime(format_name: str, thread_id: int) -> ToolRuntime:
    return ToolRuntime(
        state={},
        context=None,
        config={"configurable": {"thread_id": f"{thread_id}::task:{format_name}"}},
        stream_writer=None,
        tool_call_id=format_name,
        store=None,
    )


async def _verify(
    sandbox: FakeSandboxSession,
    workspace_id: int,
    *,
    format_name: str,
    primary_path: str,
    preview_path: str,
) -> None:
    await write_receipt(
        sandbox,
        VerificationReceipt(
            workspace_id=workspace_id,
            session_id=sandbox.session_id,
            format=format_name,
            primary_path=primary_path,
            primary_sha256=sha256_bytes(sandbox.files[primary_path]),
            preview_path=preview_path,
            preview_sha256=sha256_bytes(sandbox.files[preview_path]),
            page_count=1,
            visual="clean",
            issued_at=int(time.time()),
        ),
        SECRET,
    )


@pytest.mark.parametrize(
    ("format_name", "mime_type"),
    [
        ("docx", DOCX_MIME),
        ("pptx", PPTX_MIME),
    ],
)
async def test_office_tool_create_revise_revision_workspace_and_purge(
    db_session,
    db_workspace,
    artifact_thread,
    patched_embed_texts,
    monkeypatch,
    format_name,
    mime_type,
):
    del patched_embed_texts
    backend = MemoryBackend()
    primary_path = f"/workspace/report.{format_name}"
    preview_path = "/tmp/report.pdf"
    sandbox = FakeSandboxSession(
        {
            primary_path: _office_bytes(format_name, "first"),
            preview_path: b"%PDF-preview",
        }
    )
    await _verify(
        sandbox,
        db_workspace.id,
        format_name=format_name,
        primary_path=primary_path,
        preview_path=preview_path,
    )

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
    monkeypatch.setattr(save_artifact_tool, "get_registry", get_registry)
    monkeypatch.setattr(save_artifact_tool, "shielded_async_session", session_context)
    monkeypatch.setattr(save_artifact_tool.app_config, "SECRET_KEY", SECRET)
    monkeypatch.setattr(load_revision_tool, "get_registry", get_registry)
    monkeypatch.setattr(load_revision_tool, "shielded_async_session", session_context)
    monkeypatch.setattr(load_revision_tool, "get_storage_backend", lambda *_: backend)
    monkeypatch.setattr(
        load_revision_tool,
        "uuid4",
        lambda: type("Uuid", (), {"hex": f"{format_name}-revision"})(),
    )
    tool = save_artifact_tool.create_save_artifact_tool(db_workspace.id)
    runtime = _runtime(format_name, artifact_thread.id)
    assert "source_path" not in tool.args
    assert "preview_path" not in tool.args

    sandbox.files[primary_path] = _office_bytes(format_name, "changed-before-save")
    rejected = await tool.coroutine(
        title="Report",
        markdown_representation="# Report\n\nFirst version",
        path=primary_path,
        runtime=runtime,
    )
    assert "changed after verification" in str(rejected)

    await _verify(
        sandbox,
        db_workspace.id,
        format_name=format_name,
        primary_path=primary_path,
        preview_path=preview_path,
    )
    created_command = await tool.coroutine(
        title="Report",
        markdown_representation="# Report\n\nFirst version",
        path=primary_path,
        runtime=runtime,
    )
    created = json.loads(created_command.update["messages"][0].content)
    artifact_id = created["artifact_id"]

    assert [(file["role"], file["mime_type"]) for file in created["files"]] == [
        ("primary", mime_type),
        ("preview", "application/pdf"),
    ]
    load_tool = load_revision_tool.create_load_artifact_for_revision_tool(
        workspace_id=db_workspace.id
    )
    loaded = await load_tool.coroutine(artifact_id=artifact_id, runtime=runtime)
    revision_dir = f"/workspace/artifact-revisions/{artifact_id}/{format_name}-revision"
    assert loaded["format"] == format_name
    assert loaded["primary_path"] == f"{revision_dir}/current.{format_name}"
    assert loaded["markdown_path"] == f"{revision_dir}/context.md"
    assert loaded["expected_output_path"] == f"{revision_dir}/revised.{format_name}"
    assert loaded["artifact_id"] == artifact_id
    assert loaded["expected_generation"] == 1
    assert f"artifact_id={artifact_id}" in loaded["save_instruction"]
    assert sandbox.files[loaded["primary_path"]] == _office_bytes(
        format_name, "changed-before-save"
    )
    assert sandbox.files[loaded["markdown_path"]] == b"# Report\n\nFirst version"
    assert loaded["primary_path"] != primary_path

    revised_path = loaded["expected_output_path"]
    sandbox.files[revised_path] = _office_bytes(format_name, "second")
    sandbox.files[preview_path] = b"%PDF-preview-2"
    await _verify(
        sandbox,
        db_workspace.id,
        format_name=format_name,
        primary_path=revised_path,
        preview_path=preview_path,
    )
    revised_command = await tool.coroutine(
        title="Report",
        markdown_representation="# Report\n\nSecond version",
        path=revised_path,
        artifact_id=artifact_id,
        expected_generation=loaded["expected_generation"],
        runtime=runtime,
    )
    revised = json.loads(revised_command.update["messages"][0].content)

    assert revised["artifact_id"] == artifact_id
    assert revised["generation"] == 2
    assert (
        await db_session.scalar(
            select(func.count(Artifact.id)).where(Artifact.id == artifact_id)
        )
        == 1
    )
    assert (
        await db_session.scalar(
            select(func.count(ArtifactFile.id)).where(
                ArtifactFile.artifact_id == artifact_id
            )
        )
        == 2
    )
    stored_files = (
        await db_session.scalars(
            select(ArtifactFile).where(ArtifactFile.artifact_id == artifact_id)
        )
    ).all()
    assert {file.role for file in stored_files} == {
        ArtifactFileRole.PRIMARY,
        ArtifactFileRole.PREVIEW,
    }

    artifact = await db_session.get(Artifact, artifact_id)
    document = await db_session.get(Document, artifact.document_id)
    assert document.source_markdown == "# Report\n\nSecond version"
    assert (
        await db_session.scalar(
            select(func.count(Chunk.id)).where(
                Chunk.document_id == document.id,
                Chunk.content.ilike("%Second version%"),
            )
        )
        > 0
    )
    await purge_document_blobs(
        db_session,
        document_ids=[artifact.document_id],
        backend=backend,
    )
    assert backend.data == {}
