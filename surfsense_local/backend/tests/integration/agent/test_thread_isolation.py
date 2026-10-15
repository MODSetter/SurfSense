"""Each agent thread sees only its own folder, through the real opencode."""

import asyncio
import json

import psutil
import pytest
from sqlalchemy import Engine

from modules.agent.agent_threads import live_instances
from modules.documents.models import Document, DocumentStatus, DocumentType
from shared.db import create_session_factory
from tests.integration.agent.conftest import AgentAPI
from tests.integration.agent.test_agent_threads import open_thread, send, thread_folder

pytestmark = pytest.mark.integration


def _note(
    engine: Engine, workspace_id: int, title: str, text: str, folder_id=None
) -> int:
    with create_session_factory(engine)() as session:
        note = Document(
            workspace_id=workspace_id,
            title=title,
            document_type=DocumentType.NOTE,
            status=DocumentStatus.READY,
            content=text,
            folder_id=folder_id,
        )
        session.add(note)
        session.commit()
        return note.id


async def _folder(api: AgentAPI, name: str) -> int:
    reply = await api.http.post(
        f"/workspaces/{api.workspace_id}/folders", json={"name": name}
    )
    assert reply.status_code == 201, reply.text
    return reply.json()["id"]


def _tool_results(request: dict) -> str:
    return json.dumps([m for m in request["messages"] if m["role"] == "tool"])


def _calls(*calls: dict) -> tuple[str, str]:
    return ("calls", json.dumps(list(calls)))


async def test_a_thread_cannot_read_or_grep_another_threads_sources(
    agent_api: AgentAPI, engine: Engine
) -> None:
    """Outside its own folder every path is refused, however it is spelled."""
    ours = _note(engine, agent_api.workspace_id, "Plan", "We ship on Friday.")
    theirs = _note(engine, agent_api.workspace_id, "Memo", "We ship on Monday.")
    first, second = await open_thread(agent_api), await open_thread(agent_api)
    await send(agent_api, second["id"], "Hello", document_ids=[theirs])
    their_file = (
        thread_folder(agent_api.workspace_id, second["id"])
        / "sources"
        / f"Memo [{theirs}].md"
    )
    assert their_file.is_file()
    agent_api.model.replies = [
        _calls(
            {"name": "read", "arguments": {"filePath": str(their_file)}},
            {"name": "grep", "arguments": {"pattern": "Monday", "path": ".."}},
        ),
        ("text", "Done."),
    ]
    before = len(agent_api.model.requests)

    await send(agent_api, first["id"], "Read the memo", document_ids=[ours])

    results = _tool_results(agent_api.model.requests[before + 1])
    assert "Monday" not in results.replace('"pattern": "Monday"', "")
    assert "We ship on Monday" not in results


async def test_glob_lists_only_the_threads_sources_even_in_a_folder_named_hidden(
    agent_api: AgentAPI, engine: Engine
) -> None:
    """grep and glob skip hidden entries, so a leading dot is dropped from a folder's name."""
    hidden = await _folder(agent_api, ".hidden")
    ours = _note(engine, agent_api.workspace_id, "Plan", "Friday.", hidden)
    theirs = _note(engine, agent_api.workspace_id, "Memo", "Monday.")
    thread = await open_thread(agent_api)
    agent_api.model.replies = [
        ("call", json.dumps({"name": "glob", "arguments": {"pattern": "**/*.md"}})),
        ("text", "Listed."),
    ]
    before = len(agent_api.model.requests)

    await send(
        agent_api, thread["id"], "List them", source_scope={"folder_ids": [hidden]}
    )

    results = _tool_results(agent_api.model.requests[before + 1])
    assert f"Library/hidden/Plan [{ours}].md" in results.replace("\\\\", "/")
    assert f"Memo [{theirs}]" not in results


async def test_a_folder_named_like_an_instruction_file_gives_no_instructions(
    agent_api: AgentAPI, engine: Engine
) -> None:
    """opencode reads AGENTS.md beside any file it opens; a user's folder is not one."""
    named = await _folder(agent_api, "AGENTS.md")
    ours = _note(engine, agent_api.workspace_id, "Plan", "Friday.", named)
    thread = await open_thread(agent_api)
    path = f"sources/Library/AGENTS.md_/Plan [{ours}].md"
    agent_api.model.replies = [
        ("call", json.dumps({"name": "read", "arguments": {"filePath": path}})),
        ("text", "Read."),
    ]
    before = len(agent_api.model.requests)

    await send(agent_api, thread["id"], "Read it", source_scope={"folder_ids": [named]})

    results = _tool_results(agent_api.model.requests[before + 1])
    assert "Friday." in results
    assert "Instructions from" not in results


async def test_a_thread_cannot_change_a_text_every_thread_links(
    agent_api: AgentAPI, engine: Engine
) -> None:
    """Each thread's view of a text is the one cached file: only the edit rules keep it whole."""
    plan = _note(engine, agent_api.workspace_id, "Plan", "We ship on Friday.")
    first, second = await open_thread(agent_api), await open_thread(agent_api)
    await send(agent_api, second["id"], "Hello", document_ids=[plan])
    ours = thread_folder(agent_api.workspace_id, first["id"])
    view = f"sources/Plan [{plan}].md"
    agent_api.model.replies = [
        _calls(
            {
                "name": "edit",
                "arguments": {
                    "filePath": str(ours / view),
                    "oldString": "Friday",
                    "newString": "Sunday",
                },
            },
            {
                "name": "write",
                "arguments": {"filePath": str(ours / view), "content": "Sunday."},
            },
            {
                "name": "write",
                "arguments": {
                    "filePath": str(ours / "outputs" / "notes.md"),
                    "content": "Mine.",
                },
            },
        ),
        ("text", "Done."),
    ]
    before = len(agent_api.model.requests)

    await send(agent_api, first["id"], "Change the date", document_ids=[plan])

    results = _tool_results(agent_api.model.requests[before + 1])
    assert results.count("prevents you from using this specific tool call") == 2
    theirs = thread_folder(agent_api.workspace_id, second["id"]) / view
    assert theirs.read_text(encoding="utf-8") == "We ship on Friday."
    assert (ours / view).read_text(encoding="utf-8") == "We ship on Friday."
    assert (ours / "outputs" / "notes.md").read_text(encoding="utf-8") == "Mine."


# Turns measured beyond the first, which warms opencode up.
MEASURED_THREADS = 8


async def test_memory_one_threads_instance_holds_after_a_turn(
    agent_api: AgentAPI,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A measurement: each thread's instance, with its MCP client, stays until the thread is deleted."""
    monkeypatch.setattr(live_instances, "LIVE_INSTANCES", MEASURED_THREADS + 1)
    warm = await open_thread(agent_api)
    await send(agent_api, warm["id"], "Hello")
    running = agent_api.electron.running
    assert running is not None
    process = psutil.Process(running.process.pid)
    await asyncio.sleep(1)
    before = process.memory_info().rss

    threads = []
    for _ in range(MEASURED_THREADS):
        threads.append(await open_thread(agent_api))
        await send(agent_api, threads[-1]["id"], "Hello")
    await asyncio.sleep(1)
    grown = process.memory_info().rss
    for thread in threads:
        deleted = await agent_api.http.delete(f"/chat/threads/{thread['id']}")
        assert deleted.status_code == 204
    await asyncio.sleep(1)
    after = process.memory_info().rss

    each = (grown - before) / MEASURED_THREADS
    freed = (grown - after) / MEASURED_THREADS
    with capsys.disabled():
        print(  # noqa: T201
            f"\nopencode RSS per thread instance after a turn: {each / 2**20:.1f} MB; "
            f"deleting the thread freed {freed / 2**20:.1f} MB of it"
        )
    # Loose: the spec revisits an idle-instance cap past 5 MB; this fails only far beyond it.
    assert each < 64 * 2**20
