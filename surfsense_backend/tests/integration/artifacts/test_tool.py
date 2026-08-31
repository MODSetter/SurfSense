import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from langchain.tools import ToolRuntime
from sqlalchemy import func, select

from app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.tools import (
    load_artifact_for_revision as load_revision_tool,
    save_artifact as save_artifact_tool,
)
from app.artifacts import service
from app.artifacts.persistence import Artifact
from app.artifacts.service import ArtifactFileInput, save_artifact
from app.db import Chunk, Document

from .test_service import MemoryBackend

pytestmark = pytest.mark.integration


def _runtime(thread_id: int) -> ToolRuntime:
    return ToolRuntime(
        state={},
        context=None,
        config={"configurable": {"thread_id": f"{thread_id}::task:call-tool"}},
        stream_writer=None,
        tool_call_id="call-tool",
        store=None,
    )


async def test_tool_persists_and_indexes_artifact_document_immediately(
    db_session, db_workspace, artifact_thread, patched_embed_texts, monkeypatch
):
    del patched_embed_texts
    backend = MemoryBackend()
    monkeypatch.setattr(service, "get_storage_backend", lambda *_: backend)
    monkeypatch.setattr(
        service, "knowledge_store_enabled_for", AsyncMock(return_value=False)
    )

    @asynccontextmanager
    async def session_context():
        yield db_session

    monkeypatch.setattr(save_artifact_tool, "shielded_async_session", session_context)
    tool = save_artifact_tool.create_save_artifact_tool(workspace_id=db_workspace.id)

    command = await tool.coroutine(
        title="Legacy artifact",
        markdown_representation="# Legacy artifact\n\nimmediate-search-hit-term",
        runtime=_runtime(artifact_thread.id),
    )
    payload = json.loads(command.update["messages"][0].content)

    assert payload["status"] == "saved"
    assert payload["artifact_id"]
    assert payload["generation"] == 1
    assert payload["files"] == []
    assert (
        await db_session.scalar(
            select(func.count(Artifact.id)).where(Artifact.id == payload["artifact_id"])
        )
        == 1
    )
    assert (
        await db_session.scalar(
            select(func.count(Chunk.id))
            .join(Document, Chunk.document_id == Document.id)
            .join(Artifact, Artifact.document_id == Document.id)
            .where(
                Artifact.id == payload["artifact_id"],
                Chunk.content.ilike("%immediate-search-hit-term%"),
            )
        )
        > 0
    )


async def test_load_artifact_for_revision_restores_primary_and_markdown(
    db_session, db_workspace, artifact_thread, patched_embed_texts, monkeypatch
):
    del patched_embed_texts
    backend = MemoryBackend()
    monkeypatch.setattr(service, "get_storage_backend", lambda *_: backend)
    monkeypatch.setattr(
        service, "knowledge_store_enabled_for", AsyncMock(return_value=False)
    )
    saved = await save_artifact(
        db_session,
        workspace_id=db_workspace.id,
        thread_id=artifact_thread.id,
        tool_call_id="create",
        title="Restorable",
        markdown_representation="# Restorable",
        files=[
            ArtifactFileInput(b"%PDF", "out.pdf", "application/pdf"),
        ],
    )

    @asynccontextmanager
    async def session_context():
        yield db_session

    class Sandbox:
        def __init__(self):
            self.writes = {}

        async def run_command(self, _command):
            return type("Result", (), {"ok": True})()

        async def write_file(self, path, data):
            self.writes[path] = data

    sandbox = Sandbox()

    class Registry:
        async def get_session(self, _thread_id, _workspace_id):
            return sandbox

    async def get_registry():
        return Registry()

    monkeypatch.setattr(load_revision_tool, "shielded_async_session", session_context)
    monkeypatch.setattr(load_revision_tool, "get_storage_backend", lambda *_: backend)
    monkeypatch.setattr(load_revision_tool, "get_registry", get_registry)
    monkeypatch.setattr(
        load_revision_tool, "uuid4", lambda: type("Uuid", (), {"hex": "revision"})()
    )

    tool = load_revision_tool.create_load_artifact_for_revision_tool(
        workspace_id=db_workspace.id
    )
    loaded = await tool.coroutine(
        artifact_id=saved.artifact_id,
        runtime=_runtime(artifact_thread.id),
    )
    revision_dir = f"/workspace/artifact-revisions/{saved.artifact_id}/revision"

    assert loaded == {
        "artifact_id": saved.artifact_id,
        "format": "pdf",
        "primary_path": f"{revision_dir}/current.pdf",
        "markdown_path": f"{revision_dir}/context.md",
        "expected_output_path": f"{revision_dir}/revised.pdf",
        "expected_generation": saved.generation,
        "revision_instruction": load_revision_tool._REVISION_INSTRUCTIONS["pdf"],
        "save_instruction": (
            f"Pass artifact_id={saved.artifact_id} and "
            f"expected_generation={saved.generation} to save_artifact so this "
            "revision replaces the existing artifact."
        ),
    }
    assert sandbox.writes[f"{revision_dir}/current.pdf"] == b"%PDF"
    assert sandbox.writes[f"{revision_dir}/context.md"] == b"# Restorable"


async def test_mindmap_revision_uses_png_extension(
    db_session, db_workspace, artifact_thread, patched_embed_texts, monkeypatch
):
    del patched_embed_texts
    backend = MemoryBackend()
    monkeypatch.setattr(service, "get_storage_backend", lambda *_: backend)
    monkeypatch.setattr(
        service, "knowledge_store_enabled_for", AsyncMock(return_value=False)
    )
    saved = await save_artifact(
        db_session,
        workspace_id=db_workspace.id,
        thread_id=artifact_thread.id,
        tool_call_id="create-map",
        title="Restorable map",
        markdown_representation="# Root\n- Child",
        files=[
            ArtifactFileInput(b"PNG", "out.PNG", "image/png"),
        ],
        format="mindmap",
    )

    @asynccontextmanager
    async def session_context():
        yield db_session

    class Sandbox:
        def __init__(self):
            self.writes = {}

        async def run_command(self, _command):
            return type("Result", (), {"ok": True})()

        async def write_file(self, path, data):
            self.writes[path] = data

    sandbox = Sandbox()

    class Registry:
        async def get_session(self, _thread_id, _workspace_id):
            return sandbox

    async def get_registry():
        return Registry()

    monkeypatch.setattr(load_revision_tool, "shielded_async_session", session_context)
    monkeypatch.setattr(load_revision_tool, "get_storage_backend", lambda *_: backend)
    monkeypatch.setattr(load_revision_tool, "get_registry", get_registry)
    monkeypatch.setattr(
        load_revision_tool,
        "uuid4",
        lambda: type("Uuid", (), {"hex": "mindmap-revision"})(),
    )

    tool = load_revision_tool.create_load_artifact_for_revision_tool(
        workspace_id=db_workspace.id
    )
    loaded = await tool.coroutine(
        artifact_id=saved.artifact_id,
        runtime=_runtime(artifact_thread.id),
    )
    revision_dir = f"/workspace/artifact-revisions/{saved.artifact_id}/mindmap-revision"

    assert loaded["primary_path"] == f"{revision_dir}/current.png"
    assert loaded["expected_output_path"] == f"{revision_dir}/revised.png"
    assert (
        loaded["revision_instruction"]
        == load_revision_tool._REVISION_INSTRUCTIONS["mindmap"]
    )
