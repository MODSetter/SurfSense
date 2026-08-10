import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from langchain.tools import ToolRuntime
from sqlalchemy import func, select

from app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.tools import (
    load_artifact_source as load_source_tool,
    save_artifact as save_artifact_tool,
)
from app.artifacts import service
from app.artifacts.service import ArtifactFileInput, save_artifact
from app.db import Chunk, Document

from .test_service import MemoryBackend

pytestmark = pytest.mark.integration


def _runtime() -> ToolRuntime:
    return ToolRuntime(
        state={},
        context=None,
        config={"configurable": {"thread_id": "77::task:call-tool"}},
        stream_writer=None,
        tool_call_id="call-tool",
        store=None,
    )


async def test_tool_persists_and_indexes_legacy_artifact_immediately(
    db_session, db_workspace, patched_embed_texts, monkeypatch
):
    del patched_embed_texts
    backend = MemoryBackend()
    monkeypatch.setattr(service, "get_storage_backend", lambda: backend)
    monkeypatch.setattr(
        service, "knowledge_store_enabled_for", AsyncMock(return_value=False)
    )

    @asynccontextmanager
    async def session_context():
        yield db_session

    monkeypatch.setattr(save_artifact_tool, "shielded_async_session", session_context)
    tool = save_artifact_tool.create_save_artifact_tool(
        workspace_id=db_workspace.id, thread_id=1
    )

    command = await tool.coroutine(
        title="Legacy artifact",
        markdown_representation="# Legacy artifact\n\nimmediate-search-hit-term",
        runtime=_runtime(),
    )
    payload = json.loads(command.update["messages"][0].content)

    assert payload["status"] == "saved"
    assert payload["document_id"]
    assert payload["files"] == []
    assert (
        await db_session.scalar(
            select(func.count(Document.id)).where(Document.id == payload["document_id"])
        )
        == 1
    )
    assert (
        await db_session.scalar(
            select(func.count(Chunk.id)).where(
                Chunk.document_id == payload["document_id"],
                Chunk.content.ilike("%immediate-search-hit-term%"),
            )
        )
        > 0
    )


async def test_load_artifact_source_restores_the_current_source(
    db_session, db_workspace, monkeypatch
):
    backend = MemoryBackend()
    monkeypatch.setattr(service, "get_storage_backend", lambda: backend)
    monkeypatch.setattr(
        service, "knowledge_store_enabled_for", AsyncMock(return_value=False)
    )
    monkeypatch.setattr(service, "_index_legacy", AsyncMock())

    saved = await save_artifact(
        db_session,
        workspace_id=db_workspace.id,
        thread_id=77,
        tool_call_id="create",
        title="Restorable",
        markdown_representation="# Restorable",
        files=[
            ArtifactFileInput(b"%PDF", "out.pdf", "application/pdf"),
            ArtifactFileInput(
                b"print('current')", "out.py", "text/x-python", "source"
            ),
        ],
    )

    @asynccontextmanager
    async def session_context():
        yield db_session

    class Sandbox:
        def __init__(self):
            self.writes = {}

        async def write_file(self, path, data):
            self.writes[path] = data

    sandbox = Sandbox()

    class Registry:
        async def get_session(self, _thread_id, _workspace_id):
            return sandbox

    async def get_registry():
        return Registry()

    monkeypatch.setattr(load_source_tool, "shielded_async_session", session_context)
    monkeypatch.setattr(load_source_tool, "get_storage_backend", lambda: backend)
    monkeypatch.setattr(load_source_tool, "get_registry", get_registry)

    tool = load_source_tool.create_load_artifact_source_tool(
        workspace_id=db_workspace.id, thread_id=1
    )
    path = await tool.coroutine(document_id=saved.document_id, runtime=_runtime())

    assert path == f"/workspace/artifact-{saved.document_id}-out.py"
    assert sandbox.writes[path] == b"print('current')"
