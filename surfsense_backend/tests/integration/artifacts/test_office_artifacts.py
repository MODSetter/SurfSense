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
from app.artifacts.persistence import Artifact, ArtifactFile, ArtifactFileRole
from app.artifacts.storage import purge_artifact_blobs
from app.artifacts.verification.formats.registry import DOCX_MIME, PPTX_MIME
from app.artifacts.verification.receipt import (
    VerificationReceipt,
    sha256_bytes,
    write_receipt,
)
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


def _runtime(format_name: str) -> ToolRuntime:
    return ToolRuntime(
        state={},
        context=None,
        config={"configurable": {"thread_id": f"77::task:{format_name}"}},
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
    ("format_name", "mime_type", "source_suffix"),
    [
        ("docx", DOCX_MIME, ".js"),
        ("pptx", PPTX_MIME, ".py"),
    ],
)
async def test_office_tool_create_revise_editor_contract_and_purge(
    db_session,
    db_workspace,
    monkeypatch,
    format_name,
    mime_type,
    source_suffix,
):
    backend = MemoryBackend()
    primary_path = f"/workspace/report.{format_name}"
    source_path = f"/workspace/report{source_suffix}"
    preview_path = "/tmp/report.pdf"
    sandbox = FakeSandboxSession(
        {
            primary_path: _office_bytes(format_name, "first"),
            source_path: b"version = 1",
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
    monkeypatch.setattr(service, "index_artifact", AsyncMock())
    monkeypatch.setattr(save_artifact_tool, "get_registry", get_registry)
    monkeypatch.setattr(save_artifact_tool, "shielded_async_session", session_context)
    monkeypatch.setattr(save_artifact_tool.app_config, "SECRET_KEY", SECRET)
    monkeypatch.setattr(load_source_tool, "get_registry", get_registry)
    monkeypatch.setattr(load_source_tool, "shielded_async_session", session_context)
    monkeypatch.setattr(load_source_tool, "get_storage_backend", lambda *_: backend)
    tool = save_artifact_tool.create_save_artifact_tool(db_workspace.id)
    runtime = _runtime(format_name)

    sandbox.files[primary_path] = _office_bytes(format_name, "changed-before-save")
    rejected = await tool.coroutine(
        title="Report",
        markdown_representation="# Report\n\nFirst version",
        path=primary_path,
        source_path=source_path,
        preview_path=preview_path,
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
        source_path=source_path,
        preview_path=preview_path,
        runtime=runtime,
    )
    created = json.loads(created_command.update["messages"][0].content)
    artifact_id = created["artifact_id"]

    assert [(file["role"], file["mime_type"]) for file in created["files"]] == [
        ("primary", mime_type),
        ("preview", "application/pdf"),
    ]
    load_tool = load_source_tool.create_load_artifact_source_tool(
        workspace_id=db_workspace.id
    )
    loaded = await load_tool.coroutine(artifact_id=artifact_id, runtime=runtime)
    loaded_path = f"/workspace/artifact-{artifact_id}-report{source_suffix}"
    assert loaded["source_path"] == loaded_path
    assert loaded["artifact_id"] == artifact_id
    assert loaded["expected_generation"] == 1
    assert f"artifact_id={artifact_id}" in loaded["save_instruction"]
    assert sandbox.files[loaded_path] == b"version = 1"

    sandbox.files[primary_path] = _office_bytes(format_name, "second")
    sandbox.files[source_path] = sandbox.files[loaded_path] + b"\nversion = 2"
    sandbox.files[preview_path] = b"%PDF-preview-2"
    await _verify(
        sandbox,
        db_workspace.id,
        format_name=format_name,
        primary_path=primary_path,
        preview_path=preview_path,
    )
    revised_command = await tool.coroutine(
        title="Report",
        markdown_representation="# Report\n\nSecond version",
        path=primary_path,
        source_path=source_path,
        preview_path=preview_path,
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
        == 3
    )
    stored_source = await db_session.scalar(
        select(ArtifactFile).where(
            ArtifactFile.artifact_id == artifact_id,
            ArtifactFile.role == ArtifactFileRole.SOURCE,
        )
    )
    assert stored_source.original_filename == f"report{source_suffix}"

    await purge_artifact_blobs(
        db_session,
        artifact_ids=[artifact_id],
        backend=backend,
    )
    assert backend.data == {}
