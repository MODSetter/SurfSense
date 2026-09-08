"""Chat end to end: retrieve, stream a cited reply, and persist both turns."""

import json

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine

from modules.documents.models import Document, DocumentType
from modules.llm.models import ModelRole, SelectedModel
from modules.workspaces.models import Workspace
from shared.db import create_session_factory
from worker.ingestion import run

pytestmark = pytest.mark.integration

FINANCE = "Quarterly revenue climbed after the spring product launch."


def _seed(engine: Engine) -> tuple[int, int]:
    """A workspace with one ingested doc and a chosen chat model."""
    with create_session_factory(engine)() as session:
        workspace = Workspace(name="Notes")
        session.add(workspace)
        session.flush()
        doc = Document(
            workspace_id=workspace.id,
            title="note",
            document_type=DocumentType.NOTE,
            content=FINANCE,
        )
        session.add(doc)
        session.add(
            SelectedModel(
                role=ModelRole.GENERATION, provider="ollama", name="qwen3:1.7b"
            )
        )
        session.commit()
        ids = (workspace.id, doc.id)

    run(ids[1])
    return ids


async def _open_thread(client: AsyncClient, workspace_id: int) -> int:
    reply = await client.post(f"/workspaces/{workspace_id}/chat/threads", json={})
    return reply.json()["id"]


async def _send(client: AsyncClient, thread_id: int, text: str) -> list[dict]:
    events: list[dict] = []
    async with client.stream(
        "POST", f"/chat/threads/{thread_id}/messages", json={"text": text}
    ) as reply:
        assert reply.status_code == 200
        assert reply.headers["content-type"].startswith("text/event-stream")
        saw_done = False
        async for line in reply.aiter_lines():
            if not line.startswith("data: "):
                continue
            payload = line[len("data: ") :]
            if payload == "[DONE]":
                saw_done = True
                break
            events.append(json.loads(payload))
    assert saw_done, "the stream must end with the [DONE] sentinel"
    return events


async def test_a_thread_can_be_renamed(client: AsyncClient) -> None:
    """A manual title is trimmed, persisted, and constrained at the API boundary."""
    workspace = (await client.post("/workspaces", json={"name": "w"})).json()
    thread_id = await _open_thread(client, workspace["id"])

    renamed = await client.patch(
        f"/chat/threads/{thread_id}", json={"title": "  Banking fees  "}
    )

    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Banking fees"
    listed = (await client.get(f"/workspaces/{workspace['id']}/chat/threads")).json()
    assert listed[0]["title"] == "Banking fees"
    assert (
        await client.patch(f"/chat/threads/{thread_id}", json={"title": "   "})
    ).status_code == 422


async def test_a_message_streams_a_grounded_reply(
    client: AsyncClient, engine: Engine, real_model: object, ollama_server: list[dict]
) -> None:
    """Deltas arrive, the citation tail names the source doc, both turns persist."""
    workspace_id, doc_id = _seed(engine)
    thread_id = await _open_thread(client, workspace_id)

    events = await _send(client, thread_id, "what happened to revenue?")

    accepted = events[0]
    assert accepted["type"] == "accepted"
    assert accepted["user_message_id"] > 0
    assert accepted["assistant_message_id"] > 0

    catalog = events[1]
    assert catalog["type"] == "citation-catalog"
    assert len(catalog["items"]) == 1
    assert catalog["items"][0]["source_id"] == 1
    assert catalog["items"][0]["document_id"] == doc_id

    title = events[2]
    assert title == {"type": "thread-title-update", "title": "Revenue Growth"}
    assert (
        next(event["type"] for event in events if event["type"] == "delta") == "delta"
    )

    deltas = [event["text"] for event in events if event["type"] == "delta"]
    assert "".join(deltas) == "Revenue climbed after the launch [citation:1]."

    citations = next(event for event in events if event["type"] == "citations")
    assert any(cite["document_id"] == doc_id for cite in citations["items"])
    assert citations["items"][0]["source_id"] == 1

    stored = (await client.get(f"/chat/threads/{thread_id}/messages")).json()
    assert [message["role"] for message in stored] == ["user", "assistant"]
    assert [message["id"] for message in stored] == [
        accepted["user_message_id"],
        accepted["assistant_message_id"],
    ]
    assert (
        stored[1]["content"]["text"] == "Revenue climbed after the launch [citation:1]."
    )
    assert stored[1]["content"]["citations"]
    threads = (await client.get(f"/workspaces/{workspace_id}/chat/threads")).json()
    assert threads[0]["title"] == "Revenue Growth"
    assert ollama_server[0]["think"] is False
    assert ollama_server[0]["options"] == {"num_predict": 12, "temperature": 0}
    assert "options" not in ollama_server[1]


async def test_a_followup_carries_the_earlier_turn(
    client: AsyncClient, engine: Engine, real_model: object, ollama_server: list[dict]
) -> None:
    """The second message hands the model the first turn as history."""
    workspace_id, _ = _seed(engine)
    thread_id = await _open_thread(client, workspace_id)

    await _send(client, thread_id, "first question")
    ollama_server.clear()
    await _send(client, thread_id, "second question")

    assert len(ollama_server) == 1
    sent = ollama_server[-1]["messages"]
    assert sent[0]["role"] == "system"
    assert sent[-1] == {"role": "user", "content": "second question"}
    assert "first question" in [message["content"] for message in sent]


async def test_title_failure_does_not_block_the_answer(
    client: AsyncClient,
    engine: Engine,
    real_model: object,
    ollama_server: list[dict],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Naming is best effort; its failure must not consume or fail the chat turn."""

    async def fail_title(*_args: object) -> None:
        raise RuntimeError("title model failed")

    monkeypatch.setattr("modules.chat.router.generate_title", fail_title)
    workspace_id, _ = _seed(engine)
    thread_id = await _open_thread(client, workspace_id)

    events = await _send(client, thread_id, "what happened?")

    assert not any(event["type"] == "thread-title-update" for event in events)
    assert (
        "".join(event["text"] for event in events if event["type"] == "delta")
        == "Revenue climbed after the launch [citation:1]."
    )
    threads = (await client.get(f"/workspaces/{workspace_id}/chat/threads")).json()
    assert threads[0]["title"] == "New chat"


async def test_a_thread_with_no_model_selected_is_a_409(client: AsyncClient) -> None:
    """Refused before retrieval, so the frontend can route the user to setup."""
    workspace = (await client.post("/workspaces", json={"name": "w"})).json()
    thread_id = await _open_thread(client, workspace["id"])

    reply = await client.post(
        f"/chat/threads/{thread_id}/messages", json={"text": "hi"}
    )

    assert reply.status_code == 409


async def test_missing_embedding_assets_are_an_actionable_503(
    client: AsyncClient, engine: Engine
) -> None:
    """A dev setup omission is reported before retrieval crashes with a generic 500."""
    with create_session_factory(engine)() as session:
        session.add(
            SelectedModel(
                role=ModelRole.GENERATION, provider="ollama", name="qwen3:1.7b"
            )
        )
        session.commit()
    workspace = (await client.post("/workspaces", json={"name": "w"})).json()
    thread_id = await _open_thread(client, workspace["id"])

    reply = await client.post(
        f"/chat/threads/{thread_id}/messages", json={"text": "hi"}
    )

    assert reply.status_code == 503
    assert reply.json()["detail"] == (
        "local embedding model is not installed; "
        "run `uv run scripts/fetch_embedding_model.py`"
    )
