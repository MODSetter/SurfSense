"""A chat thread that uses the agent, from opening it to deleting it, through the API."""

import asyncio
import json
from collections.abc import Awaitable, Callable

import pytest
from sqlalchemy import select

from modules.chat.models import ChatThread
from modules.documents.models import Document, DocumentStatus, DocumentType
from shared.config import get_agent_settings, get_storage_settings
from shared.db import create_db_engine, create_session_factory
from tests.integration.agent.conftest import AgentAPI

pytestmark = pytest.mark.integration

Frame = dict
OnFrame = Callable[[Frame], Awaitable[None]]


async def open_thread(api: AgentAPI, title: str = "New chat") -> dict:
    """Open a thread the way the chat panel does."""
    reply = await api.http.post(
        f"/workspaces/{api.workspace_id}/chat/threads", json={"title": title}
    )
    reply.raise_for_status()
    return reply.json()


async def send(
    api: AgentAPI, thread_id: int, text: str, on_frame: OnFrame | None = None
) -> list[Frame]:
    """Send one message and read its stream to the end; every frame, in order."""
    frames: list[Frame] = []
    async with api.http.stream(
        "POST", f"/chat/threads/{thread_id}/messages", json={"text": text}
    ) as reply:
        assert reply.status_code == 200, await reply.aread()
        async for line in reply.aiter_lines():
            if not line.startswith("data: "):
                continue
            data = line.removeprefix("data: ")
            if data == "[DONE]":
                frames.append({"type": "done"})
                break
            frame = json.loads(data)
            frames.append(frame)
            if on_frame is not None:
                await on_frame(frame)
    return frames


def of_type(frames: list[Frame], kind: str) -> list[Frame]:
    """The frames of one type."""
    return [frame for frame in frames if frame["type"] == kind]


def working_folder(workspace_id: int):
    """Where the workspace's agent works."""
    return get_storage_settings().agent_working_dir(workspace_id)


async def test_a_new_thread_uses_the_agent_when_the_model_may(
    agent_api: AgentAPI,
) -> None:
    """The engine is the model's to decide, at the moment the thread is opened."""
    thread = await open_thread(agent_api, "Research")

    assert thread["uses_agent"] is True
    async with agent_api.opencode() as opencode:
        assert (
            len(await opencode.session_ids(working_folder(agent_api.workspace_id))) == 1
        )


async def test_without_the_agent_a_new_thread_is_a_chat(
    agent_api: AgentAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No model is on the tested list, so only the developer switch lets one in."""
    monkeypatch.setattr(get_agent_settings(), "agent_untested_models", False)

    thread = await open_thread(agent_api)

    assert thread["uses_agent"] is False
    assert agent_api.electron.starts == 0


async def test_a_message_streams_the_agents_reply(agent_api: AgentAPI) -> None:
    """The chat's own frames carry the agent's reply, from accepted to done."""
    agent_api.model.replies = [("text", "Revenue rose in Q3.")]
    thread = await open_thread(agent_api)

    frames = await send(agent_api, thread["id"], "What happened in Q3?")

    assert frames[0]["type"] == "accepted"
    assert "".join(f["text"] for f in of_type(frames, "delta")) == "Revenue rose in Q3."
    assert of_type(frames, "completed")[0]["text"] == "Revenue rose in Q3."
    assert frames[-1] == {"type": "done"}


async def test_the_sources_are_in_the_folder_before_the_turn(
    agent_api: AgentAPI,
) -> None:
    """opencode reads the workspace through its own tools, so the text must be on disk first."""
    thread = await open_thread(agent_api)
    with create_session_factory(
        create_db_engine(get_storage_settings().database_path)
    )() as session:
        note = Document(
            workspace_id=agent_api.workspace_id,
            title="Plan",
            document_type=DocumentType.NOTE,
            status=DocumentStatus.READY,
            content="Ship on Friday.",
        )
        session.add(note)
        session.commit()
        note_id = note.id

    await send(agent_api, thread["id"], "When do we ship?")

    source = working_folder(agent_api.workspace_id) / "sources" / f"Plan [{note_id}].md"
    assert source.read_text(encoding="utf-8") == "Ship on Friday."


async def test_a_shell_command_waits_for_the_users_yes(agent_api: AgentAPI) -> None:
    """The command runs only after the user's answer reaches opencode through the API."""
    agent_api.model.replies = [("bash", "echo approved"), ("text", "It printed.")]
    thread = await open_thread(agent_api)

    async def approve(frame: Frame) -> None:
        if frame["type"] == "permission-request":
            assert frame["command"] == "echo approved"
            reply = await agent_api.http.post(
                f"/chat/threads/{thread['id']}/permissions/{frame['id']}",
                json={"reply": "once"},
            )
            assert reply.status_code == 204

    frames = await send(agent_api, thread["id"], "Run it", approve)

    steps = of_type(frames, "agent-step")
    assert steps[-1]["tool"] == "bash"
    assert steps[-1]["status"] == "completed"
    assert steps[-1]["output"].strip() == "approved"
    assert of_type(frames, "completed")[0]["text"] == "It printed."


async def test_a_refused_shell_command_never_runs(agent_api: AgentAPI) -> None:
    """A refusal fails the call and ends the turn, which still closes cleanly."""
    agent_api.model.replies = [("bash", "echo refused")]
    thread = await open_thread(agent_api)

    async def refuse(frame: Frame) -> None:
        if frame["type"] == "permission-request":
            await agent_api.http.post(
                f"/chat/threads/{thread['id']}/permissions/{frame['id']}",
                json={"reply": "reject"},
            )

    frames = await send(agent_api, thread["id"], "Run it", refuse)

    assert of_type(frames, "agent-step")[-1]["status"] == "error"
    assert frames[-1] == {"type": "done"}


async def test_listing_the_thread_reads_its_turns_from_opencode(
    agent_api: AgentAPI,
) -> None:
    """One reply per turn, however many steps the agent took to write it."""
    agent_api.model.replies = [("bash", "echo listed"), ("text", "Listed.")]
    thread = await open_thread(agent_api)

    async def approve(frame: Frame) -> None:
        if frame["type"] == "permission-request":
            await agent_api.http.post(
                f"/chat/threads/{thread['id']}/permissions/{frame['id']}",
                json={"reply": "once"},
            )

    await send(agent_api, thread["id"], "List it", approve)
    reply = await agent_api.http.get(f"/chat/threads/{thread['id']}/messages")

    user, assistant = reply.json()
    assert (user["role"], user["content"]["text"]) == ("user", "List it")
    assert (assistant["role"], assistant["content"]["text"]) == ("assistant", "Listed.")
    assert [step["tool"] for step in assistant["content"]["steps"]] == ["bash"]


async def test_closing_the_stream_stops_the_turn(agent_api: AgentAPI) -> None:
    """Leaving the thread is the stop button: the agent must not keep working unseen."""
    agent_api.model.replies = [("stall", "Thinking about")]
    thread = await open_thread(agent_api)
    folder = working_folder(agent_api.workspace_id)

    async with agent_api.http.stream(
        "POST", f"/chat/threads/{thread['id']}/messages", json={"text": "Go"}
    ) as reply:
        async for line in reply.aiter_lines():
            if '"type": "delta"' in line:
                break

    session_id = await _session_of(thread["id"])
    async with agent_api.opencode() as opencode, asyncio.timeout(15):
        while await opencode.status(folder, session_id) != "idle":
            await asyncio.sleep(0.2)


async def test_deleting_the_thread_deletes_its_session(agent_api: AgentAPI) -> None:
    """A deleted thread leaves no conversation behind in opencode."""
    thread = await open_thread(agent_api)
    session_id = await _session_of(thread["id"])

    reply = await agent_api.http.delete(f"/chat/threads/{thread['id']}")

    assert reply.status_code == 204
    async with agent_api.opencode() as opencode:
        assert session_id not in await opencode.session_ids(
            working_folder(agent_api.workspace_id)
        )


async def test_deleting_the_workspace_deletes_its_sessions(agent_api: AgentAPI) -> None:
    """The workspace's folder goes with it, and so must the sessions that worked there."""
    thread = await open_thread(agent_api)
    session_id = await _session_of(thread["id"])
    folder = working_folder(agent_api.workspace_id)

    reply = await agent_api.http.delete(f"/workspaces/{agent_api.workspace_id}")

    assert reply.status_code == 204
    async with agent_api.opencode() as opencode:
        assert session_id not in await opencode.session_ids(folder)


async def _session_of(thread_id: int) -> str:
    """The opencode session a thread stores."""
    with create_session_factory(
        create_db_engine(get_storage_settings().database_path)
    )() as session:
        session_id = session.scalar(
            select(ChatThread.opencode_session_id).where(ChatThread.id == thread_id)
        )
    assert session_id
    return session_id
