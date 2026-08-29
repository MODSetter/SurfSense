"""Integration: xlsx save path with real receipt + DB (sandbox/storage boundaries only)."""

from __future__ import annotations

import json
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
from app.artifacts.verification import service as verify_service
from app.artifacts.verification.formats.registry import XLSX_MIME
from app.db import ChatVisibility, Chunk, Document, NewChatThread
from app.file_storage.service import purge_document_blobs
from tests.utils.fake_sandbox import FakeSandboxSession

from .test_service import MemoryBackend

pytestmark = pytest.mark.integration
SECRET = "test-secret"

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _xlsx_bytes(label: str) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("_rels/.rels", "<Relationships/>")
        archive.writestr(
            "xl/workbook.xml",
            f"""<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="{MAIN_NS}" xmlns:r="{OFFICE_REL_NS}">
  <sheets>
    <sheet name="Sheet1" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>""",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            f"""<Relationships xmlns="{PKG_REL_NS}">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
    Target="worksheets/sheet1.xml"/>
</Relationships>""",
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            f"""<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="{MAIN_NS}">
  <sheetData>
    <row r="1"><c r="A1"><v>{label}</v></c></row>
  </sheetData>
</worksheet>""",
        )
    return output.getvalue()


def _runtime(thread_id: int) -> ToolRuntime:
    return ToolRuntime(
        state={},
        context=None,
        config={"configurable": {"thread_id": f"{thread_id}::task:xlsx"}},
        stream_writer=None,
        tool_call_id="xlsx",
        store=None,
    )


async def test_xlsx_tool_create_revise_without_persisted_preview(
    db_session,
    db_workspace,
    db_user,
    monkeypatch,
):
    thread = NewChatThread(
        title="XLSX artifact chat",
        workspace_id=db_workspace.id,
        created_by_id=db_user.id,
        visibility=ChatVisibility.PRIVATE,
    )
    db_session.add(thread)
    await db_session.flush()

    backend = MemoryBackend()
    primary_path = "/workspace/budget.xlsx"
    first_bytes = _xlsx_bytes("first")
    sandbox = FakeSandboxSession({primary_path: first_bytes})

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
        lambda: type("Uuid", (), {"hex": "xlsx-revision"})(),
    )

    verified = await verify_service.verify_artifact(
        sandbox,
        primary_path,
        workspace_id=db_workspace.id,
        vision_llm=None,
        secret_key=SECRET,
    )
    assert verified.verified
    assert verified.preview_path is None
    assert all(
        "soffice" not in command and "pdftoppm" not in command
        for command in sandbox.commands
    )

    tool = save_artifact_tool.create_save_artifact_tool(db_workspace.id)
    runtime = _runtime(thread.id)
    assert "source_path" not in tool.args
    assert "preview_path" not in tool.args

    sandbox.files[primary_path] = _xlsx_bytes("changed-before-save")
    rejected = await tool.coroutine(
        title="Budget",
        markdown_representation="# Budget\n\nFirst version",
        path=primary_path,
        runtime=runtime,
    )
    assert "changed after verification" in str(rejected)

    sandbox.files[primary_path] = first_bytes
    reverified = await verify_service.verify_artifact(
        sandbox,
        primary_path,
        workspace_id=db_workspace.id,
        vision_llm=None,
        secret_key=SECRET,
    )
    assert reverified.verified

    created_command = await tool.coroutine(
        title="Budget",
        markdown_representation="# Budget\n\nFirst version",
        path=primary_path,
        runtime=runtime,
    )
    created = json.loads(created_command.update["messages"][0].content)
    artifact_id = created["artifact_id"]

    assert [(file["role"], file["mime_type"]) for file in created["files"]] == [
        ("primary", XLSX_MIME),
    ]
    assert not any(file["role"] == "preview" for file in created["files"])
    assert not any(file["role"] == "source" for file in created["files"])

    load_tool = load_revision_tool.create_load_artifact_for_revision_tool(
        workspace_id=db_workspace.id
    )
    loaded = await load_tool.coroutine(artifact_id=artifact_id, runtime=runtime)
    revision_dir = f"/workspace/artifact-revisions/{artifact_id}/xlsx-revision"
    assert loaded["format"] == "xlsx"
    assert loaded["artifact_id"] == artifact_id
    assert loaded["primary_path"] == f"{revision_dir}/current.xlsx"
    assert loaded["markdown_path"] == f"{revision_dir}/context.md"
    assert loaded["expected_output_path"] == f"{revision_dir}/revised.xlsx"
    assert loaded["expected_generation"] == 1
    assert sandbox.files[loaded["primary_path"]] == first_bytes
    assert sandbox.files[loaded["markdown_path"]] == b"# Budget\n\nFirst version"
    assert loaded["primary_path"] != primary_path

    revised_path = loaded["expected_output_path"]
    sandbox.files[revised_path] = _xlsx_bytes("second")
    revised_ok = await verify_service.verify_artifact(
        sandbox,
        revised_path,
        workspace_id=db_workspace.id,
        vision_llm=None,
        secret_key=SECRET,
    )
    assert revised_ok.verified

    revised_command = await tool.coroutine(
        title="Budget",
        markdown_representation="# Budget\n\nSecond version",
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
        == 1
    )
    stored_files = (
        await db_session.scalars(
            select(ArtifactFile).where(ArtifactFile.artifact_id == artifact_id)
        )
    ).all()
    assert [(file.role, file.original_filename) for file in stored_files] == [
        (ArtifactFileRole.PRIMARY, "revised.xlsx")
    ]

    artifact = await db_session.get(Artifact, artifact_id)
    document = await db_session.get(Document, artifact.document_id)
    assert document.source_markdown == "# Budget\n\nSecond version"
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
