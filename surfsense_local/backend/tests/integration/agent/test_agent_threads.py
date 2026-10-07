"""A chat thread that uses the agent, from opening it to deleting it, through the API."""

import asyncio
import json
import sqlite3
from collections.abc import Awaitable, Callable
from pathlib import Path

import httpx
import pytest
from sqlalchemy import Engine, select
from sqlalchemy.exc import OperationalError

from modules.agent.agent_threads import live_instances, thread_messages
from modules.agent.agent_threads import turn as agent_turn
from modules.artifacts.models import Artifact
from modules.chat import router as chat_router
from modules.chat.models import ChatThread
from modules.chunks.models import Chunk
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.llm.capability.agent_trial import set_agent_trial
from modules.llm.model_type import ModelType
from modules.llm.models import SelectedModel
from shared.config import get_agent_settings, get_storage_settings
from shared.db import create_db_engine, create_session_factory
from tests.integration.agent.conftest import AGENT_MODEL, AgentAPI
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


def thread_folder(workspace_id: int, thread_id: int) -> Path:
    """Where one agent thread works."""
    return get_storage_settings().thread_working_dir(workspace_id, thread_id)


async def test_a_new_thread_uses_the_agent_when_the_model_may(
    agent_api: AgentAPI,
) -> None:
    """The engine is the model's to decide, at the moment the thread is opened."""
    thread = await open_thread(agent_api, "Research")

    assert thread["uses_agent"] is True
    folder = thread_folder(agent_api.workspace_id, thread["id"])
    async with agent_api.opencode() as opencode:
        (session_id,) = await opencode.session_ids(folder)
        # The thread's own folder, which holds only the sources it may use.
        assert Path(await opencode.session_directory(session_id)) == folder


async def test_without_the_agent_a_new_thread_is_a_chat(
    agent_api: AgentAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A model not measured and not opted in gets the chat without the developer switch."""
    monkeypatch.setattr(get_agent_settings(), "agent_untested_models", False)

    thread = await open_thread(agent_api)

    assert thread["uses_agent"] is False
    assert agent_api.electron.starts == 0


async def test_a_message_streams_the_agents_reply(agent_api: AgentAPI) -> None:
    """The chat's own frames carry the agent's reply, from accepted to done."""
    agent_api.model.replies = [("text", "Revenue rose in Q3.")]
    thread = await open_thread(agent_api)

    frames = await send(agent_api, thread["id"], "What happened in Q3?")

    assert [frame["type"] for frame in frames[:2]] == ["agent-preparing", "accepted"]
    assert "".join(f["text"] for f in of_type(frames, "delta")) == "Revenue rose in Q3."
    assert of_type(frames, "completed")[0]["text"] == "Revenue rose in Q3."
    assert frames[-1] == {"type": "done"}


async def test_a_thread_is_read_back_off_the_event_loop(
    agent_api: AgentAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A long thread's turns take tens of milliseconds to build; a reply
    streaming meanwhile would wait on them."""
    agent_api.model.replies = [("text", "Revenue rose in Q3.")]
    thread = await open_thread(agent_api)
    await send(agent_api, thread["id"], "What happened in Q3?")
    on_loop: list[bool] = []

    def recorded(work: Callable) -> Callable:
        def run(*args: object) -> object:
            try:
                asyncio.get_running_loop()
                on_loop.append(True)
            except RuntimeError:
                on_loop.append(False)
            return work(*args)

        return run

    for name in ("searched_chunks", "thread_turns"):
        monkeypatch.setattr(
            thread_messages, name, recorded(getattr(thread_messages, name))
        )

    turns = await agent_api.http.get(f"/chat/threads/{thread['id']}/messages")

    assert turns.json()[-1]["content"]["text"] == "Revenue rose in Q3."
    assert on_loop == [False, False]


async def test_an_unexpected_error_inside_the_stream_still_ends_it(
    agent_api: AgentAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The sync runs inside the stream: a failure there must not leave the chat waiting."""

    def database_fails(*_args: object) -> None:
        raise OperationalError("SELECT", {}, sqlite3.OperationalError("disk I/O error"))

    monkeypatch.setattr(agent_turn, "sync_thread_folder", database_fails)
    thread = await open_thread(agent_api)

    frames = await send(agent_api, thread["id"], "Hello")

    (error,) = of_type(frames, "error")
    assert error["kind"] == "unknown"
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

    folder = thread_folder(agent_api.workspace_id, thread["id"])
    source = folder / "sources" / f"Plan [{note_id}].md"
    assert source.read_text(encoding="utf-8") == "Ship on Friday."


async def test_a_turn_says_how_many_sources_it_prepares_before_it_syncs_them(
    agent_api: AgentAPI,
) -> None:
    """A big scope's first sync takes about 30 s, and the thread must not look stuck meanwhile."""
    thread = await open_thread(agent_api)
    _note(agent_api.workspace_id, "Plan", "Ship on Friday.")
    _note(agent_api.workspace_id, "Memo", "Ship on Monday.")

    frames = await send(agent_api, thread["id"], "When do we ship?")

    assert frames[0] == {"type": "agent-preparing", "count": 2}


async def test_sources_that_cannot_be_prepared_end_the_turn_with_an_error_frame(
    agent_api: AgentAPI,
) -> None:
    """The sync runs inside the stream, so its failure is said there, and nothing is sent."""
    thread = await open_thread(agent_api)
    folder = thread_folder(agent_api.workspace_id, thread["id"])
    (folder / "sources").rmdir()
    (folder / "sources").write_text("in the way", encoding="utf-8")

    frames = await send(agent_api, thread["id"], "When do we ship?")

    assert [frame["type"] for frame in frames] == ["agent-preparing", "error", "done"]
    assert agent_api.model.requests == []


def _note(workspace_id: int, title: str, text: str) -> int:
    with create_session_factory(
        create_db_engine(get_storage_settings().database_path)
    )() as session:
        note = Document(
            workspace_id=workspace_id,
            title=title,
            document_type=DocumentType.NOTE,
            status=DocumentStatus.READY,
            content=text,
        )
        session.add(note)
        session.commit()
        return note.id


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


async def test_the_thread_list_says_a_turn_needs_approval(agent_api: AgentAPI) -> None:
    """A window that is elsewhere learns the agent waits on the user, not that it
    is still writing."""
    agent_api.model.replies = [REPEATED, ("text", "Listed.")]
    thread = await open_thread(agent_api)
    states: list[dict | None] = []

    async def state() -> dict | None:
        listed = await agent_api.http.get(
            f"/workspaces/{agent_api.workspace_id}/chat/threads"
        )
        return next(t["run_state"] for t in listed.json() if t["id"] == thread["id"])

    async def approve(frame: Frame) -> None:
        if frame["type"] == "permission-request":
            states.append(await state())
            await agent_api.http.post(
                f"/chat/threads/{thread['id']}/permissions/{frame['id']}",
                json={"reply": "once"},
            )
        elif frame["type"] == "permission-replied":
            states.append(await state())

    await send(agent_api, thread["id"], "List them", approve)

    assert states == [
        {"state": "needs-approval", "position": None},
        {"state": "running", "position": None},
    ]


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


async def test_a_turn_keeps_going_after_its_window_hangs_up(
    agent_api: AgentAPI,
) -> None:
    """Leaving the thread drops the follower, never the turn: following it again
    replays everything it sent, then the rest."""
    agent_api.model.replies = [("stall", "Thinking about")]
    thread = await open_thread(agent_api)

    await hang_up_mid_turn(agent_api, thread["id"])
    following = asyncio.create_task(follow(agent_api, thread["id"]))
    await asyncio.sleep(0.5)
    agent_api.model.release.set()
    frames = await asyncio.wait_for(following, 30)

    assert frames[0]["type"] == "agent-preparing"
    assert "".join(f["text"] for f in of_type(frames, "delta")) == "Thinking about"
    assert of_type(frames, "completed")[0]["text"] == "Thinking about"
    assert frames[-1] == {"type": "done"}


async def test_a_thread_takes_one_turn_at_a_time(agent_api: AgentAPI) -> None:
    """A second message while the agent works would interleave two turns."""
    agent_api.model.replies = [("stall", "Thinking about")]
    thread = await open_thread(agent_api)

    await hang_up_mid_turn(agent_api, thread["id"])
    second = await agent_api.http.post(
        f"/chat/threads/{thread['id']}/messages", json={"text": "And?"}
    )
    agent_api.model.release.set()
    await follow(agent_api, thread["id"])

    assert second.status_code == 409


async def test_stop_ends_the_turn_in_opencode(agent_api: AgentAPI) -> None:
    """Stop is a route now, not a hang-up: the session is idle when it returns."""
    agent_api.model.replies = [("stall", "Thinking about")]
    thread = await open_thread(agent_api)
    folder = thread_folder(agent_api.workspace_id, thread["id"])

    await hang_up_mid_turn(agent_api, thread["id"])
    stopped = await agent_api.http.post(f"/chat/threads/{thread['id']}/run/stop")
    session_id = await _session_of(thread["id"])
    async with agent_api.opencode() as opencode:
        status = await opencode.status(folder, session_id)
    followed = await agent_api.http.get(f"/chat/threads/{thread['id']}/run")
    agent_api.model.release.set()

    assert stopped.status_code == 204
    assert status == "idle"
    assert followed.status_code == 404


async def test_a_stopped_reply_reads_back_stopped_with_its_text(
    agent_api: AgentAPI,
) -> None:
    """After a reload the thread still says the user cut this reply short."""
    agent_api.model.replies = [("stall", "Thinking about")]
    thread = await open_thread(agent_api)

    await hang_up_mid_turn(agent_api, thread["id"])
    await agent_api.http.post(f"/chat/threads/{thread['id']}/run/stop")
    agent_api.model.release.set()
    reply = (await agent_api.http.get(f"/chat/threads/{thread['id']}/messages")).json()[
        -1
    ]

    assert reply["content"]["text"] == "Thinking about"
    assert reply["content"]["ending"] == {"type": "stopped"}


async def test_quitting_keeps_the_text_and_reads_back_interrupted(
    agent_api: AgentAPI,
) -> None:
    """opencode marks a quit as it marks a stop; only SurfSense knows the app went away."""
    agent_api.model.replies = [("stall", "Thinking about")]
    thread = await open_thread(agent_api)

    await hang_up_mid_turn(agent_api, thread["id"])
    stopped = await agent_api.http.post("/chat/runs/stop-all")
    agent_api.model.release.set()
    reply = (await agent_api.http.get(f"/chat/threads/{thread['id']}/messages")).json()[
        -1
    ]

    assert stopped.status_code == 204
    assert reply["content"]["text"] == "Thinking about"
    assert reply["content"]["ending"] == {"type": "interrupted"}


async def hang_up_mid_turn(api: AgentAPI, thread_id: int) -> None:
    """Send a message and close the stream once the reply has started."""
    async with api.http.stream(
        "POST", f"/chat/threads/{thread_id}/messages", json={"text": "Go"}
    ) as reply:
        assert reply.status_code == 200, await reply.aread()
        async for line in reply.aiter_lines():
            if '"type": "delta"' in line:
                return


async def follow(api: AgentAPI, thread_id: int, after: int = 0) -> list[Frame]:
    """Follow the thread's run from `after` to its end."""
    frames: list[Frame] = []
    async with api.http.stream(
        "GET", f"/chat/threads/{thread_id}/run", params={"after": after}
    ) as reply:
        assert reply.status_code == 200, await reply.aread()
        async for line in reply.aiter_lines():
            if not line.startswith("data: "):
                continue
            data = line.removeprefix("data: ")
            if data == "[DONE]":
                frames.append({"type": "done"})
                break
            frames.append(json.loads(data))
    return frames


async def test_deleting_the_thread_deletes_its_session_instance_and_folder(
    agent_api: AgentAPI, engine: Engine
) -> None:
    """A deleted thread leaves no conversation, no instance and no files behind; its documents stay."""
    thread = await open_thread(agent_api)
    folder = thread_folder(agent_api.workspace_id, thread["id"])
    await send(agent_api, thread["id"], "Hello")
    assert "surfsense" in await _tool_servers(agent_api, folder)
    session_id = await _session_of(thread["id"])
    artifact = _artifact(engine, agent_api.workspace_id, thread["id"])

    reply = await agent_api.http.delete(f"/chat/threads/{thread['id']}")

    assert reply.status_code == 204
    async with agent_api.opencode() as opencode:
        assert session_id not in await opencode.session_ids(folder)
    # A fresh instance starts without the thread's tools: the old one was disposed.
    assert "surfsense" not in await _tool_servers(agent_api, folder)
    assert not folder.exists()
    listed = await agent_api.http.get(f"/workspaces/{agent_api.workspace_id}/artifacts")
    assert [a["id"] for a in listed.json()] == [artifact]


async def test_a_new_thread_never_starts_in_what_a_deleted_one_left(
    agent_api: AgentAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SQLite gives a deleted newest thread's id to the next, and with it the folder's path."""
    thread = await open_thread(agent_api)
    await send(agent_api, thread["id"], "Hello")
    left = thread_folder(agent_api.workspace_id, thread["id"]) / "outputs" / "notes.md"
    left.write_text("From sources the next chat may not use.", encoding="utf-8")
    # As on Windows while a file in it is still open.
    monkeypatch.setattr(chat_router, "remove_thread_folder", lambda _folder: None)
    deleted = await agent_api.http.delete(f"/chat/threads/{thread['id']}")
    assert deleted.status_code == 204

    reopened = await open_thread(agent_api)

    assert reopened["id"] == thread["id"]
    assert reopened["uses_agent"] is True
    assert not left.exists()


async def test_a_thread_started_in_the_shared_folder_reads_back_but_takes_no_turn(
    agent_api: AgentAPI,
) -> None:
    """Its session sits where every thread's folder is in reach, and a session cannot move."""
    thread = await open_thread(agent_api)
    shared = get_storage_settings().agent_working_dir(agent_api.workspace_id)
    agent_api.model.replies = [("text", "Revenue rose.")]
    async with agent_api.opencode() as opencode:
        legacy = await opencode.create_session(shared, "Before folders")
        async with asyncio.timeout(30):
            await opencode.send_turn(shared, legacy, "Q3?", model=AGENT_MODEL)
            while (
                await opencode.status(shared, legacy) != "idle"
                or len(await opencode.messages(shared, legacy)) < 2
            ):
                await asyncio.sleep(0.2)
    _store_session(thread["id"], legacy)

    refused = await agent_api.http.post(
        f"/chat/threads/{thread['id']}/messages", json={"text": "And Q4?"}
    )
    history = await agent_api.http.get(f"/chat/threads/{thread['id']}/messages")

    assert refused.status_code == 409
    assert refused.json()["detail"] == (
        "This agent chat was started before each chat kept its own sources. "
        "Start a new chat to continue."
    )
    assert history.status_code == 200
    assert [turn["content"]["text"] for turn in history.json()] == [
        "Q3?",
        "Revenue rose.",
    ]
    assert len(agent_api.model.requests) == 1


async def test_a_thread_whose_session_opencode_lost_offers_a_new_chat(
    agent_api: AgentAPI,
) -> None:
    """Such a thread can never take a turn again; the refusal the app knows shows its new-chat button."""
    thread = await open_thread(agent_api)
    folder = thread_folder(agent_api.workspace_id, thread["id"])
    async with agent_api.opencode() as opencode:
        await opencode.delete_session(folder, await _session_of(thread["id"]))

    refused = await agent_api.http.post(
        f"/chat/threads/{thread['id']}/messages", json={"text": "Hello"}
    )

    assert refused.status_code == 409
    assert refused.json()["detail"] == (
        "This agent chat was started before each chat kept its own sources. "
        "Start a new chat to continue."
    )


async def test_a_session_lost_after_a_turn_is_refused_like_one_lost_before(
    agent_api: AgentAPI,
) -> None:
    """A session this run already checked can still vanish, as when opencode's data is cleared."""
    thread = await open_thread(agent_api)
    await send(agent_api, thread["id"], "Hello")
    folder = thread_folder(agent_api.workspace_id, thread["id"])
    async with agent_api.opencode() as opencode:
        await opencode.delete_session(folder, await _session_of(thread["id"]))

    refused = await agent_api.http.post(
        f"/chat/threads/{thread['id']}/messages", json={"text": "Again"}
    )

    assert refused.status_code == 409
    assert refused.json()["detail"] == (
        "This agent chat was started before each chat kept its own sources. "
        "Start a new chat to continue."
    )


async def test_past_the_cap_the_least_recently_used_instance_is_freed(
    agent_api: AgentAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each thread's instance holds about 30 MB after a turn, and opencode frees none on its own."""
    monkeypatch.setattr(live_instances, "LIVE_INSTANCES", 1)
    first, second = await open_thread(agent_api), await open_thread(agent_api)

    await send(agent_api, first["id"], "Hello")
    await send(agent_api, second["id"], "Hello")

    # A fresh instance starts without the thread's tools: the old one was disposed.
    first_folder = thread_folder(agent_api.workspace_id, first["id"])
    assert "surfsense" not in await _tool_servers(agent_api, first_folder)
    second_folder = thread_folder(agent_api.workspace_id, second["id"])
    assert "surfsense" in await _tool_servers(agent_api, second_folder)
    assert of_type(await send(agent_api, first["id"], "Again"), "completed")


async def test_an_instance_whose_turn_is_streaming_is_never_freed(
    agent_api: AgentAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A turn waiting on the model or on an approval keeps its instance past the cap."""
    monkeypatch.setattr(live_instances, "LIVE_INSTANCES", 1)
    agent_api.model.replies = [("stall", "Reading"), ("text", "Hi.")]
    streaming, other = await open_thread(agent_api), await open_thread(agent_api)
    started = asyncio.Event()

    async def on_frame(frame: Frame) -> None:
        if frame["type"] == "delta":
            started.set()

    turn = asyncio.create_task(send(agent_api, streaming["id"], "Hello", on_frame))
    await asyncio.wait_for(started.wait(), 30)
    await send(agent_api, other["id"], "Hello")

    folder = thread_folder(agent_api.workspace_id, streaming["id"])
    assert "surfsense" in await _tool_servers(agent_api, folder)
    agent_api.model.release.set()
    assert of_type(await turn, "completed")


async def test_two_threads_at_once_keep_their_own_tools(agent_api: AgentAPI) -> None:
    """Each thread's instance holds the address naming it, so neither turn uses the other's."""
    first, second = await open_thread(agent_api), await open_thread(agent_api)

    await send(agent_api, first["id"], "Hello")
    await send(agent_api, second["id"], "Hello")

    for thread in (first, second):
        folder = thread_folder(agent_api.workspace_id, thread["id"])
        servers = await _tool_servers(agent_api, folder)
        assert servers["surfsense"]["status"] == "connected"


async def test_deleting_the_workspace_deletes_its_sessions(agent_api: AgentAPI) -> None:
    """The workspace's folder goes with it, and so must the sessions that worked there."""
    thread = await open_thread(agent_api)
    session_id = await _session_of(thread["id"])
    folder = thread_folder(agent_api.workspace_id, thread["id"])

    reply = await agent_api.http.delete(f"/workspaces/{agent_api.workspace_id}")

    assert reply.status_code == 204
    async with agent_api.opencode() as opencode:
        assert session_id not in await opencode.session_ids(folder)


async def _tool_servers(api: AgentAPI, folder: Path) -> dict:
    """The MCP servers the folder's opencode instance holds, by name."""
    async with httpx.AsyncClient(
        base_url=api.opencode_url, auth=("opencode", api.password)
    ) as http:
        reply = await http.get("/mcp", params={"directory": str(folder)})
    reply.raise_for_status()
    return reply.json()


def _store_session(thread_id: int, session_id: str) -> None:
    """Point a thread at a session, as one opened before thread folders is."""
    with create_session_factory(
        create_db_engine(get_storage_settings().database_path)
    )() as session:
        session.get(ChatThread, thread_id).opencode_session_id = session_id
        session.commit()


def _artifact(engine: Engine, workspace_id: int, thread_id: int) -> int:
    """A ready Studio artifact the thread made, which its deletion must keep."""
    with create_session_factory(engine)() as session:
        document = Document(
            workspace_id=workspace_id,
            title="Quiz",
            document_type=DocumentType.ARTIFACT,
            status=DocumentStatus.READY,
            content="Q1?",
        )
        session.add(document)
        session.flush()
        artifact = Artifact(
            workspace_id=workspace_id,
            document_id=document.id,
            chat_thread_id=thread_id,
            format="quiz",
        )
        session.add(artifact)
        session.commit()
        return artifact.id


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


def _set_text_model(*, name: str | None = None, trial: bool | None = None) -> None:
    """Change the chat model or its agent trial, as Settings would."""
    with create_session_factory(
        create_db_engine(get_storage_settings().database_path)
    )() as session:
        selected = session.get(SelectedModel, ModelType.TEXT_GEN)
        if name is not None:
            selected.name = name
        if trial is not None:
            set_agent_trial(selected, trial)
        session.commit()


async def test_an_agent_threads_next_turn_follows_the_models_level_and_opt_in(
    agent_api: AgentAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A thread keeps its engine, but its model must still be one the agent may run."""
    thread = await open_thread(agent_api)
    monkeypatch.setattr(get_agent_settings(), "agent_untested_models", False)
    url = f"/chat/threads/{thread['id']}/messages"

    not_opted_in = await agent_api.http.post(url, json={"text": "Hello"})
    _set_text_model(trial=True)
    agent_api.model.replies = [("text", "Hi.")]
    opted_in = await send(agent_api, thread["id"], "Hello")
    _set_text_model(name="qwen/qwen3.5-9b")
    measured_to_fail = await agent_api.http.post(url, json={"text": "Again"})

    assert not_opted_in.status_code == 409
    assert "cannot run the agent" in not_opted_in.json()["detail"]
    assert of_type(opted_in, "completed")[0]["text"] == "Hi."
    assert measured_to_fail.status_code == 409
    assert "cannot run the agent" in measured_to_fail.json()["detail"]
    assert len(agent_api.model.requests) == 1
