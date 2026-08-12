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
    db_session,
    db_workspace,
    artifact_thread_factory,
    patched_embed_texts,
    monkeypatch,
):
    del patched_embed_texts
    backend = MemoryBackend()
    monkeypatch.setattr(service, "get_storage_backend", lambda *_: backend)
    monkeypatch.setattr(
        service, "knowledge_store_enabled_for", AsyncMock(return_value=False)
    )
    first_thread = await artifact_thread_factory("First artifact thread")
    second_thread = await artifact_thread_factory("Second artifact thread")
    first = await save_artifact(
        db_session,
        workspace_id=db_workspace.id,
        thread_id=first_thread.id,
        tool_call_id="first",
        title="First chat artifact",
        markdown_representation="# First",
        files=[],
    )
    second = await save_artifact(
        db_session,
        workspace_id=db_workspace.id,
        thread_id=second_thread.id,
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
        lambda: {
            "configurable": {"thread_id": f"{first_thread.id}::task:call-a"}
        },
    )
    first_result = await middleware.abefore_agent(state, SimpleNamespace())
    first_roster = first_result["messages"][0].content
    assert f"artifact_id={first.artifact_id}" in first_roster
    assert f"artifact_id={second.artifact_id}" not in first_roster

    monkeypatch.setattr(
        artifact_roster,
        "get_config",
        lambda: {
            "configurable": {"thread_id": f"{second_thread.id}::task:call-b"}
        },
    )
    second_result = await middleware.abefore_agent(state, SimpleNamespace())
    second_roster = second_result["messages"][0].content
    assert f"artifact_id={second.artifact_id}" in second_roster
    assert f"artifact_id={first.artifact_id}" not in second_roster


async def test_roster_keeps_an_explicitly_mentioned_artifact_beyond_the_cap(
    db_session,
    db_workspace,
    artifact_thread,
    patched_embed_texts,
    monkeypatch,
):
    del patched_embed_texts
    backend = MemoryBackend()
    monkeypatch.setattr(service, "get_storage_backend", lambda *_: backend)
    monkeypatch.setattr(
        service, "knowledge_store_enabled_for", AsyncMock(return_value=False)
    )
    artifacts = []
    for index in range(11):
        artifacts.append(
            await save_artifact(
                db_session,
                workspace_id=db_workspace.id,
                thread_id=artifact_thread.id,
                tool_call_id=f"call-{index}",
                title=f"Artifact {index}",
                markdown_representation=f"# Artifact {index}",
                files=[],
            )
        )

    @asynccontextmanager
    async def session_context():
        yield db_session

    monkeypatch.setattr(artifact_roster, "shielded_async_session", session_context)
    monkeypatch.setattr(
        artifact_roster,
        "get_config",
        lambda: {
            "configurable": {
                "thread_id": f"{artifact_thread.id}::task:call-roster"
            }
        },
    )
    middleware = ArtifactRosterMiddleware(workspace_id=db_workspace.id)

    ordinary = await middleware.abefore_agent(
        {"messages": [HumanMessage(content="Revise it")]},
        SimpleNamespace(),
    )
    assert (
        f"artifact_id={artifacts[0].artifact_id}" not in ordinary["messages"][0].content
    )

    mentioned = await middleware.abefore_agent(
        {
            "messages": [HumanMessage(content="Revise it")],
            "mentioned_artifact_ids": [artifacts[0].artifact_id],
        },
        SimpleNamespace(),
    )
    assert f"artifact_id={artifacts[0].artifact_id}" in mentioned["messages"][0].content


async def test_roster_query_failure_aborts_the_invocation(monkeypatch):
    @asynccontextmanager
    async def failed_session():
        raise RuntimeError("database unavailable")
        yield  # pragma: no cover

    monkeypatch.setattr(artifact_roster, "shielded_async_session", failed_session)
    monkeypatch.setattr(
        artifact_roster,
        "get_config",
        lambda: {"configurable": {"thread_id": "404::task:call-roster"}},
    )

    with pytest.raises(RuntimeError, match="database unavailable"):
        await ArtifactRosterMiddleware(workspace_id=1).abefore_agent(
            {"messages": [HumanMessage(content="Create it")]},
            SimpleNamespace(),
        )
