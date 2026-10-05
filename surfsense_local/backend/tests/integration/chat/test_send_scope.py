"""A turn's sources come from a scope the server resolves, however many there are."""

import hashlib
import json

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine

from modules.documents.models import Document, DocumentType
from modules.llm.model_type import ModelType
from modules.llm.models import SelectedModel
from modules.source_roots.managed_root import ensure_managed_root
from modules.workspaces.models import Workspace
from shared.db import create_session_factory
from worker.ingestion import run

pytestmark = pytest.mark.integration

FINANCE = "Quarterly revenue climbed after the spring product launch."


def _library(engine: Engine, contents: list[str]) -> tuple[int, list[int]]:
    """A workspace whose notes are ingested oldest first, and a chat model."""
    with create_session_factory(engine)() as session:
        workspace = Workspace(name="Notes")
        session.add(workspace)
        session.flush()
        library = ensure_managed_root(session, workspace.id)
        ids = []
        for content in contents:
            note = Document(
                workspace_id=workspace.id,
                title="note",
                document_type=DocumentType.NOTE,
                content=content,
                folder_id=library.id,
            )
            session.add(note)
            session.flush()
            ids.append(note.id)
        session.add(
            SelectedModel(
                model_type=ModelType.TEXT_GEN,
                provider="llamacpp",
                name="Qwen3-1.7B-Q4_K_M",
            )
        )
        session.commit()
        workspace_id = workspace.id
    for document_id in ids:
        run(document_id)
    return workspace_id, ids


async def _thread(
    client: AsyncClient, workspace_id: int, body: dict | None = None
) -> int:
    reply = await client.post(
        f"/workspaces/{workspace_id}/chat/threads", json=body or {}
    )
    assert reply.status_code == 201, reply.text
    return reply.json()["id"]


async def _cited(client: AsyncClient, thread_id: int, body: dict) -> set[int]:
    async with client.stream(
        "POST", f"/chat/threads/{thread_id}/messages", json=body
    ) as reply:
        assert reply.status_code == 200, await reply.aread()
        async for line in reply.aiter_lines():
            if line.startswith("data: {"):
                event = json.loads(line[len("data: ") :])
                if event["type"] == "citation-catalog":
                    catalog = {item["document_id"] for item in event["items"]}
    return catalog


async def test_every_source_is_searched_past_the_fiftieth(
    client: AsyncClient, engine: Engine, real_model: object, llamacpp_server: list
) -> None:
    """The oldest of sixty sources answers, which a 50-row id list never sent."""
    fillers = [f"Gardening tip {n}: water the tomatoes at dusk." for n in range(59)]
    workspace_id, ids = _library(engine, [FINANCE, *fillers])
    thread_id = await _thread(client, workspace_id)

    cited = await _cited(
        client,
        thread_id,
        {"text": "what happened to revenue?", "source_scope": {"all": True}},
    )

    assert ids[0] in cited


async def test_the_turn_records_its_scope_and_what_it_resolved_to(
    client: AsyncClient, engine: Engine, real_model: object, llamacpp_server: list
) -> None:
    """The turn records its scope and what it resolved to."""
    workspace_id, ids = _library(engine, [FINANCE, "The feline dozed."])
    thread_id = await _thread(client, workspace_id)
    scope = {"all": True, "excluded_document_ids": [ids[1]]}

    await _cited(client, thread_id, {"text": "revenue?", "source_scope": scope})

    stored = (await client.get(f"/chat/threads/{thread_id}/messages")).json()
    user = stored[0]["content"]
    assert user["source_scope"] == {
        "all": True,
        "folder_ids": [],
        "excluded_folder_ids": [],
        "document_ids": [],
        "excluded_document_ids": [ids[1]],
    }
    assert user["resolved"] == {
        "count": 1,
        "ids_sha256": hashlib.sha256(json.dumps([ids[0]]).encode()).hexdigest(),
    }


async def test_a_scope_sent_with_a_turn_is_kept_for_the_next(
    client: AsyncClient, engine: Engine, real_model: object, llamacpp_server: list
) -> None:
    """Ticking a box and pressing Enter cannot race: the turn stores what it used."""
    workspace_id, ids = _library(engine, [FINANCE, "Revenue fell in the autumn."])
    thread_id = await _thread(client, workspace_id)
    only_second = {"document_ids": [ids[1]]}

    await _cited(client, thread_id, {"text": "revenue?", "source_scope": only_second})
    cited = await _cited(client, thread_id, {"text": "and revenue now?"})

    assert cited == {ids[1]}
    threads = (await client.get(f"/workspaces/{workspace_id}/chat/threads")).json()
    assert threads[0]["source_scope"]["document_ids"] == [ids[1]]


async def test_ticks_made_between_turns_are_stored_with_their_counts(
    client: AsyncClient, engine: Engine
) -> None:
    """Ticks made between turns are stored with their counts."""
    with create_session_factory(engine)() as session:
        workspace = Workspace(name="w")
        session.add(workspace)
        session.flush()
        library = ensure_managed_root(session, workspace.id)
        note = Document(
            workspace_id=workspace.id,
            title="draft",
            document_type=DocumentType.NOTE,
            content="x",
            folder_id=library.id,
        )
        session.add(note)
        session.commit()
        workspace_id, note_id = workspace.id, note.id
    thread_id = await _thread(client, workspace_id)
    assert (await client.get(f"/chat/threads/{thread_id}/source-scope")).json()[
        "source_scope"
    ]["all"] is True

    stored = await client.put(
        f"/chat/threads/{thread_id}/source-scope",
        json={"document_ids": [note_id, 999_999]},
    )

    assert stored.status_code == 200
    assert stored.json()["source_scope"]["document_ids"] == [note_id]
    assert stored.json()["counts"] == {
        "ready": 0,
        "indexing": 1,
        "failed": 0,
        "removed": 1,
    }
    read = await client.get(f"/chat/threads/{thread_id}/source-scope")
    assert read.json()["source_scope"]["document_ids"] == [note_id]


async def test_a_draft_scope_resolves_without_a_thread(
    client: AsyncClient, engine: Engine
) -> None:
    """A new chat's ticks are counted before its first turn opens a thread."""
    workspace = (await client.post("/workspaces", json={"name": "w"})).json()
    await client.post(
        f"/workspaces/{workspace['id']}/documents",
        json={"title": "Draft", "content": "unindexed"},
    )

    resolved = await client.post(
        f"/workspaces/{workspace['id']}/source-scope/resolve", json={"all": True}
    )

    assert resolved.status_code == 200
    assert resolved.json()["counts"]["indexing"] == 1


async def test_a_thread_opens_with_the_drafted_scope(
    client: AsyncClient, engine: Engine
) -> None:
    """A thread opens with the drafted scope."""
    workspace = (await client.post("/workspaces", json={"name": "w"})).json()

    thread_id = await _thread(
        client, workspace["id"], {"source_scope": {"all": True, "folder_ids": []}}
    )

    read = await client.get(f"/chat/threads/{thread_id}/source-scope")
    assert read.json()["source_scope"]["all"] is True


async def test_a_scope_naming_another_workspaces_source_is_refused(
    client: AsyncClient, engine: Engine
) -> None:
    """A scope naming another workspaces source is refused."""
    mine = (await client.post("/workspaces", json={"name": "Mine"})).json()
    other = (await client.post("/workspaces", json={"name": "Other"})).json()
    note = await client.post(
        f"/workspaces/{other['id']}/documents",
        json={"title": "theirs", "content": "x"},
    )
    thread_id = await _thread(client, mine["id"])

    refused = await client.put(
        f"/chat/threads/{thread_id}/source-scope",
        json={"document_ids": [note.json()["id"]]},
    )

    assert refused.status_code == 422


async def test_an_agent_turn_gets_the_scopes_ids_even_past_a_thousand(
    client: AsyncClient, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The agent reads `document_ids`, where an omitted list means every source;
    a scope too big for the client to list must still bound the turn."""
    from fastapi.responses import StreamingResponse

    from modules.chat import router as chat_router
    from modules.chat.models import ChatThread
    from modules.documents.models import DocumentStatus

    with create_session_factory(engine)() as session:
        workspace = Workspace(name="Big")
        session.add(workspace)
        session.flush()
        library = ensure_managed_root(session, workspace.id)
        notes = [
            Document(
                workspace_id=workspace.id,
                title=f"n{n}",
                document_type=DocumentType.NOTE,
                content="x",
                status=DocumentStatus.READY,
                folder_id=library.id,
            )
            for n in range(1003)
        ]
        session.add_all(notes)
        thread = ChatThread(workspace_id=workspace.id, opencode_session_id="ses_1")
        session.add(thread)
        session.commit()
        unticked = notes[0].id
        thread_id = thread.id
    seen: list[list[int] | None] = []

    async def agent_turn(session, thread, payload, launch_key):
        seen.append(payload.document_ids)
        return StreamingResponse(iter(()))

    monkeypatch.setattr(chat_router, "agent_turn", agent_turn)

    reply = await client.post(
        f"/chat/threads/{thread_id}/messages",
        json={
            "text": "hi",
            "source_scope": {"all": True, "excluded_document_ids": [unticked]},
        },
    )

    assert reply.status_code == 200, reply.text
    assert seen[0] is not None
    assert len(seen[0]) == 1002
    assert unticked not in seen[0]
    stored = (await client.get(f"/chat/threads/{thread_id}/source-scope")).json()
    assert stored["source_scope"]["excluded_document_ids"] == [unticked]
