"""A thread moves between opencode and Claude Code when the user changes models, and stays one thread."""

import json
from pathlib import Path

import pytest
from claude_agent_sdk import get_session_info

# Claude Code's spelling of a folder as its project's name, which the SDK keeps private.
from claude_agent_sdk._internal.sessions import _canonicalize_path, _sanitize_path
from sqlalchemy import select

from modules.chat.models import ChatThread
from modules.llm.model_type import ModelType
from modules.llm.models import ProviderConnection, SelectedModel
from shared.config import get_storage_settings
from shared.db import create_db_engine, create_session_factory
from tests.claude_agent_stand_in import Say
from tests.integration.agent.claude_code.conftest import ClaudeAgent
from tests.integration.agent.conftest import AGENT_MODEL, AgentAPI
from tests.integration.agent.test_agent_threads import (
    of_type,
    open_thread,
    send,
    thread_folder,
)

pytestmark = pytest.mark.integration
SONNET = "claude-sonnet-5-5"


async def _choose_claude(api: AgentAPI, claude_on_this_machine) -> None:
    claude_on_this_machine()
    await api.http.put(
        "/egress",
        json={
            "destinations": ["host:api.anthropic.com", "host:platform.claude.com"],
            "enabled": True,
        },
    )
    connection = (
        await api.http.post("/llm/connections/claude", json={"label": "Claude"})
    ).json()
    chosen = await api.http.put(
        "/llm/selection/text_gen",
        json={
            "provider": "openai_compatible",
            "connection_id": connection["id"],
            "name": SONNET,
        },
    )
    assert chosen.status_code == 200, chosen.text


def _choose_opencodes_model() -> None:
    """Back to the remote model the harness chose, as the harness chose it."""
    with create_session_factory(
        create_db_engine(get_storage_settings().database_path)
    )() as session:
        remote = session.scalars(
            select(ProviderConnection).where(ProviderConnection.label == "Remote")
        ).one()
        selected = session.get(SelectedModel, ModelType.TEXT_GEN)
        selected.connection_id = remote.id
        selected.name = AGENT_MODEL
        session.commit()


async def test_switching_to_a_claude_plan_model_hands_the_thread_over(
    agent_api: AgentAPI, claude_on_this_machine, claude_agent: ClaudeAgent
) -> None:
    """Claude Code is told what opencode did, and the thread reads as one."""
    agent_api.model.replies = [("text", "Opencode found 12%.")]
    thread = await open_thread(agent_api, mode="agentic")
    await send(agent_api, thread["id"], "What grew in Q3?")

    await _choose_claude(agent_api, claude_on_this_machine)
    claude_agent.turns = [[Say("Claude agrees: 12%.")]]
    frames = await send(agent_api, thread["id"], "Are you sure?")

    assert of_type(frames, "completed")[0]["text"] == "Claude agrees: 12%."
    (run,) = claude_agent.started
    (sent,) = run.sent
    note, words = sent[0]["text"], sent[-1]["text"]
    assert note.startswith("<surfsense-handover>")
    assert "What grew in Q3?" in note
    assert "Opencode found 12%." in note
    assert words == "Are you sure?"
    listed = (await agent_api.http.get(f"/chat/threads/{thread['id']}/messages")).json()
    assert [turn["content"]["text"] for turn in listed] == [
        "What grew in Q3?",
        "Opencode found 12%.",
        "Are you sure?",
        "Claude agrees: 12%.",
    ]


async def test_switching_back_tells_opencode_only_what_it_missed(
    agent_api: AgentAPI, claude_on_this_machine, claude_agent: ClaudeAgent
) -> None:
    """opencode resumes its own session, given the Claude turns since its last."""
    agent_api.model.replies = [("text", "One."), ("text", "Three.")]
    thread = await open_thread(agent_api, mode="agentic")
    await send(agent_api, thread["id"], "First")
    await _choose_claude(agent_api, claude_on_this_machine)
    claude_agent.turns = [[Say("Two.")]]
    await send(agent_api, thread["id"], "Second")

    _choose_opencodes_model()
    frames = await send(agent_api, thread["id"], "Third")

    assert of_type(frames, "completed")[0]["text"] == "Three."
    asked = json.dumps(agent_api.model.requests[-1])
    assert "<surfsense-handover>" in asked
    assert "Two." in asked
    listed = (await agent_api.http.get(f"/chat/threads/{thread['id']}/messages")).json()
    assert [turn["content"]["text"] for turn in listed] == [
        "First",
        "One.",
        "Second",
        "Two.",
        "Third",
        "Three.",
    ]


async def _left_claude(
    api: AgentAPI, claude_on_this_machine, claude_agent: ClaudeAgent, home: Path
) -> tuple[dict, str, Path]:
    """A thread Claude Code ran, with Claude Code's own transcript on disk, now on opencode."""
    await _choose_claude(api, claude_on_this_machine)
    thread = await open_thread(api, mode="agentic")
    claude_agent.turns = [[Say("Two.")]]
    await send(api, thread["id"], "First")
    with create_session_factory(
        create_db_engine(get_storage_settings().database_path)
    )() as session:
        session_id = session.get_one(ChatThread, thread["id"]).claude_session_id
    folder = thread_folder(api.workspace_id, thread["id"])
    # Where Claude Code writes it, which the stand-in does not.
    project = home / "projects" / _sanitize_path(_canonicalize_path(str(folder)))
    project.mkdir(parents=True)
    line = {
        "type": "user",
        "uuid": "u1",
        "sessionId": session_id,
        "isSidechain": False,
        "timestamp": "2026-10-17T09:00:00.000Z",
        "message": {"role": "user", "content": "First"},
    }
    (project / f"{session_id}.jsonl").write_text(json.dumps(line) + "\n")
    assert get_session_info(session_id, directory=str(folder)) is not None
    _choose_opencodes_model()
    api.model.replies = [("text", "Three.")]
    await send(api, thread["id"], "Second")
    return thread, session_id, folder


async def test_deleting_a_thread_that_left_claude_code_deletes_its_claude_session(
    agent_api: AgentAPI,
    claude_on_this_machine,
    claude_agent: ClaudeAgent,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Its Claude Code is ended and Claude Code's copy of the chat deleted, as opencode's is."""
    home = tmp_path / "claude-home"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home))
    thread, session_id, folder = await _left_claude(
        agent_api, claude_on_this_machine, claude_agent, home
    )

    deleted = await agent_api.http.delete(f"/chat/threads/{thread['id']}")

    assert deleted.status_code == 204
    (run,) = claude_agent.started
    assert run.closed
    assert get_session_info(session_id, directory=str(folder)) is None


async def test_deleting_a_workspace_deletes_the_claude_session_of_a_thread_that_left(
    agent_api: AgentAPI,
    claude_on_this_machine,
    claude_agent: ClaudeAgent,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every thread Claude Code ran, not only those on it now."""
    home = tmp_path / "claude-home"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home))
    _, session_id, folder = await _left_claude(
        agent_api, claude_on_this_machine, claude_agent, home
    )

    deleted = await agent_api.http.delete(f"/workspaces/{agent_api.workspace_id}")

    assert deleted.status_code == 204
    assert get_session_info(session_id, directory=str(folder)) is None
