from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import HumanMessage

from app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.middleware import (
    artifact_roster,
)
from app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.middleware.artifact_roster import (
    ArtifactRosterMiddleware,
)
from app.artifacts import service
from app.artifacts.service import save_artifact

from .test_service import MemoryBackend

pytestmark = pytest.mark.integration


async def test_roster_resolves_each_chat_from_live_config(
    db_session, db_workspace, monkeypatch
):
    backend = MemoryBackend()
    monkeypatch.setattr(service, "get_storage_backend", lambda: backend)
    monkeypatch.setattr(
        service, "knowledge_store_enabled_for", AsyncMock(return_value=False)
    )
    monkeypatch.setattr(service, "_index_legacy", AsyncMock())

    first = await save_artifact(
        db_session,
        workspace_id=db_workspace.id,
        thread_id=101,
        tool_call_id="first",
        title="First chat artifact",
        markdown_representation="# First",
        files=[],
    )
    second = await save_artifact(
        db_session,
        workspace_id=db_workspace.id,
        thread_id=202,
        tool_call_id="second",
        title="Second chat artifact",
        markdown_representation="# Second",
        files=[],
    )

    @asynccontextmanager
    async def session_context():
        yield db_session

    monkeypatch.setattr(artifact_roster, "shielded_async_session", session_context)
    middleware = ArtifactRosterMiddleware(workspace_id=db_workspace.id)
    state = {"messages": [HumanMessage(content="Revise it")]}

    monkeypatch.setattr(
        artifact_roster,
        "get_config",
        lambda: {"configurable": {"thread_id": "101::task:call-a"}},
    )
    first_result = await middleware.abefore_agent(state, SimpleNamespace())
    first_roster = first_result["messages"][0].content
    assert f"document_id={first.document_id}" in first_roster
    assert f"document_id={second.document_id}" not in first_roster

    monkeypatch.setattr(
        artifact_roster,
        "get_config",
        lambda: {"configurable": {"thread_id": "202::task:call-b"}},
    )
    second_result = await middleware.abefore_agent(state, SimpleNamespace())
    second_roster = second_result["messages"][0].content
    assert f"document_id={second.document_id}" in second_roster
    assert f"document_id={first.document_id}" not in second_roster
