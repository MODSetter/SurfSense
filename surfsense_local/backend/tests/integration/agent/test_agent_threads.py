"""A chat thread that uses the agent, from opening it to deleting it, through the API."""

import asyncio
import json
from collections.abc import Awaitable, Callable

import pytest
from sqlalchemy import Engine, select

from modules.chat.models import ChatThread
from modules.chunks.models import Chunk
from modules.documents.models import Document, DocumentStatus, DocumentType
from shared.config import get_agent_settings, get_storage_settings
from shared.db import create_db_engine, create_session_factory
from tests.integration.agent.conftest import AgentAPI
from worker.ingestion import run

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
    api: AgentAPI,
    thread_id: int,
    text: str,
    on_frame: OnFrame | None = None,
    **fields: object,
) -> list[Frame]:
    """Send one message, with any other fields of the request, and read its stream to the end."""
    frames: list[Frame] = []
    async with api.http.stream(
        "POST", f"/chat/threads/{thread_id}/messages", json={"text": text, **fields}
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


async def test_a_thread_cannot_continue_with_a_model_that_cannot_call_tools(
    agent_api: AgentAPI,
) -> None:
    """The thread stays the agent's, and opencode would take no step with that model."""
    thread = await open_thread(agent_api)
    current = (await agent_api.http.get("/llm/selection/text_gen")).json()
    chosen = await agent_api.http.put(
        "/llm/selection/text_gen",
        json={
            "provider": "openai_compatible",
            "connection_id": current["connection_id"],
            "name": "gpt-3.5-turbo",
            "allow_unlisted": True,
        },
    )
    chosen.raise_for_status()

    reply = await agent_api.http.post(
        f"/chat/threads/{thread['id']}/messages", json={"text": "What happened in Q3?"}
    )

    assert reply.status_code == 409
    assert "new chat" in reply.json()["detail"]
    assert agent_api.model.requests == []
    turns = await agent_api.http.get(f"/chat/threads/{thread['id']}/messages")
    assert turns.json() == []


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


def ingest_note(
    engine: Engine, workspace_id: int, title: str, text: str
) -> tuple[int, int]:
    """A note taken through ingestion to ready: its id and its first chunk's."""
    with create_session_factory(engine)() as session:
        note = Document(
            workspace_id=workspace_id,
            title=title,
            document_type=DocumentType.NOTE,
            content=text,
        )
        session.add(note)
        session.commit()
        note_id = note.id
    run(note_id)
    with create_session_factory(engine)() as session:
        chunk_id = session.scalars(
            select(Chunk.id).where(Chunk.document_id == note_id)
        ).first()
    assert chunk_id is not None
    return note_id, chunk_id


SEARCH = (
    "call",
    json.dumps(
        {"name": "surfsense_search_sources", "arguments": {"query": "ship date"}}
    ),
)


async def test_the_agent_searches_the_sources_through_surfsense(
    agent_api: AgentAPI, engine: Engine, real_model: object
) -> None:
    """The model is offered SurfSense's search, calls it, and reads what it found."""
    ingest_note(
        engine, agent_api.workspace_id, "Plan 2026", "We ship on Friday 14 November."
    )
    agent_api.model.replies = [SEARCH, ("text", "On Friday.")]
    thread = await open_thread(agent_api)

    await send(agent_api, thread["id"], "When do we ship?")

    offered, answered = agent_api.model.requests[:2]
    assert "surfsense_search_sources" in [
        tool["function"]["name"] for tool in offered["tools"]
    ]
    results = [m for m in answered["messages"] if m["role"] == "tool"]
    assert "We ship on Friday 14 November." in json.dumps(results)


async def test_a_cited_passage_becomes_a_citation_and_an_invented_one_is_dropped(
    agent_api: AgentAPI, engine: Engine, real_model: object
) -> None:
    """Only a label the search returned may point at a source, as in a chat answer."""
    note_id, chunk_id = ingest_note(
        engine, agent_api.workspace_id, "Plan 2026", "We ship on Friday 14 November."
    )
    agent_api.model.replies = [
        SEARCH,
        ("text", f"We ship on Friday [{chunk_id}]. Costs fell [999999]."),
    ]
    thread = await open_thread(agent_api)

    frames = await send(agent_api, thread["id"], "When do we ship?")
    listed = await agent_api.http.get(f"/chat/threads/{thread['id']}/messages")

    text = of_type(frames, "completed")[0]["text"]
    assert f"We ship on Friday [citation:{chunk_id}]." in text
    assert "999999" not in text
    (cited,) = of_type(frames, "citations")[0]["items"]
    assert (cited["chunk_id"], cited["document_id"]) == (chunk_id, note_id)
    reply = listed.json()[-1]
    assert reply["content"]["text"] == text
    assert [c["chunk_id"] for c in reply["content"]["citations"]] == [chunk_id]


# A step that makes the same call three times is the one thing opencode still
# asks about, now the shell is denied.
GLOB = {"name": "glob", "arguments": {"pattern": "sources/*.md"}}
REPEATED = ("calls", json.dumps([GLOB] * 3))


async def test_an_approval_waits_for_the_users_yes(agent_api: AgentAPI) -> None:
    """The call goes on only after the user's answer reaches opencode through the API."""
    agent_api.model.replies = [REPEATED, ("text", "Listed.")]
    thread = await open_thread(agent_api)
    asked: list[Frame] = []

    async def approve(frame: Frame) -> None:
        if frame["type"] == "permission-request":
            asked.append(frame)
            reply = await agent_api.http.post(
                f"/chat/threads/{thread['id']}/permissions/{frame['id']}",
                json={"reply": "once"},
            )
            assert reply.status_code == 204

    frames = await send(agent_api, thread["id"], "List them", approve)

    assert [(f["permission"], f["command"]) for f in asked] == [("doom_loop", None)]
    assert of_type(frames, "agent-step")[-1]["status"] == "completed"
    assert of_type(frames, "completed")[0]["text"] == "Listed."


async def test_a_refused_approval_ends_the_turn(agent_api: AgentAPI) -> None:
    """Nothing it was asked about runs, and the stream still closes cleanly."""
    agent_api.model.replies = [REPEATED]
    thread = await open_thread(agent_api)

    async def refuse(frame: Frame) -> None:
        if frame["type"] == "permission-request":
            await agent_api.http.post(
                f"/chat/threads/{thread['id']}/permissions/{frame['id']}",
                json={"reply": "reject"},
            )

    frames = await send(agent_api, thread["id"], "List them", refuse)

    assert frames[-1] == {"type": "done"}
    assert not [f for f in of_type(frames, "agent-step") if f["status"] == "completed"]
    # The turn ended at the refusal: the model was not asked to go on.
    assert len(agent_api.model.requests) == 1


async def test_listing_the_thread_reads_its_turns_from_opencode(
    agent_api: AgentAPI,
) -> None:
    """One reply per turn, however many steps the agent took to write it."""
    agent_api.model.replies = [("call", json.dumps(GLOB)), ("text", "Listed.")]
    thread = await open_thread(agent_api)

    await send(agent_api, thread["id"], "List it")
    reply = await agent_api.http.get(f"/chat/threads/{thread['id']}/messages")

    user, assistant = reply.json()
    assert (user["role"], user["content"]["text"]) == ("user", "List it")
    assert (assistant["role"], assistant["content"]["text"]) == ("assistant", "Listed.")
    assert [step["tool"] for step in assistant["content"]["steps"]] == ["glob"]


async def test_words_before_a_tool_call_and_after_it_read_as_two_paragraphs(
    agent_api: AgentAPI,
) -> None:
    """Live, on completion and reopened, the reply never runs one step's words into the next."""
    agent_api.model.replies = [
        ("say-and-call", json.dumps({"say": "I'll list the sources.", "call": GLOB})),
        ("text", "Listed."),
    ]
    thread = await open_thread(agent_api)

    frames = await send(agent_api, thread["id"], "List them")
    stored = await agent_api.http.get(f"/chat/threads/{thread['id']}/messages")

    expected = "I'll list the sources.\n\nListed."
    assert "".join(f["text"] for f in of_type(frames, "delta")) == expected
    assert of_type(frames, "completed")[0]["text"] == expected
    assert stored.json()[-1]["content"]["text"] == expected


SUMMARY = "## Objective\nList the sources.\n\n## Next Move\nAnswer."


async def test_a_compaction_mid_turn_is_not_the_reply(agent_api: AgentAPI) -> None:
    """opencode summarises the session for itself when the window fills; the user sees the answer."""
    agent_api.model.replies = [
        ("call-filling-the-window", json.dumps(GLOB)),
        ("text", SUMMARY),
        ("text", "Listed."),
    ]
    thread = await open_thread(agent_api)

    frames = await send(agent_api, thread["id"], "List it")

    # The summary was asked for, so the compaction really happened.
    assert len(agent_api.model.requests) == 3
    assert "".join(f["text"] for f in of_type(frames, "delta")) == "Listed."
    assert of_type(frames, "completed")[0]["text"] == "Listed."
    stored = (await agent_api.http.get(f"/chat/threads/{thread['id']}/messages")).json()
    assert [(turn["role"], turn["content"]["text"]) for turn in stored] == [
        ("user", "List it"),
        ("assistant", "Listed."),
    ]
    assert [step["tool"] for step in stored[1]["content"]["steps"]] == ["glob"]


async def test_a_request_the_model_refuses_as_too_long_is_compacted_not_failed(
    agent_api: AgentAPI,
) -> None:
    """opencode reports the overflow, summarises, sends the user's message again and answers."""
    agent_api.model.replies = [
        ("too-long", ""),
        ("text", SUMMARY),
        ("text", "Listed."),
    ]
    thread = await open_thread(agent_api)

    frames = await send(agent_api, thread["id"], "List it")

    assert len(agent_api.model.requests) == 3
    assert of_type(frames, "error") == []
    assert of_type(frames, "completed")[0]["text"] == "Listed."
    stored = (await agent_api.http.get(f"/chat/threads/{thread['id']}/messages")).json()
    assert [(turn["role"], turn["content"]["text"]) for turn in stored] == [
        ("user", "List it"),
        ("assistant", "Listed."),
    ]


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
