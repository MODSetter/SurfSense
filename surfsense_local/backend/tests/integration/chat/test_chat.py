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


async def test_a_message_streams_a_grounded_reply(
    client: AsyncClient, engine: Engine, real_model: object, ollama_server: list[dict]
) -> None:
    """Deltas arrive, the citation tail names the source doc, both turns persist."""
    workspace_id, doc_id = _seed(engine)
    thread_id = await _open_thread(client, workspace_id)

    events = await _send(client, thread_id, "what happened to revenue?")

    deltas = [event["text"] for event in events if event["type"] == "delta"]
    assert "".join(deltas) == "Revenue climbed after the launch [1]."

    citations = next(event for event in events if event["type"] == "citations")
    assert any(cite["document_id"] == doc_id for cite in citations["items"])

    stored = (await client.get(f"/chat/threads/{thread_id}/messages")).json()
    assert [message["role"] for message in stored] == ["user", "assistant"]
    assert stored[1]["content"]["text"] == "Revenue climbed after the launch [1]."
    assert stored[1]["content"]["citations"]


async def test_a_followup_carries_the_earlier_turn(
    client: AsyncClient, engine: Engine, real_model: object, ollama_server: list[dict]
) -> None:
    """The second message hands the model the first turn as history."""
    workspace_id, _ = _seed(engine)
    thread_id = await _open_thread(client, workspace_id)

    await _send(client, thread_id, "first question")
    ollama_server.clear()
    await _send(client, thread_id, "second question")

    sent = ollama_server[-1]["messages"]
    assert sent[0]["role"] == "system"
    assert sent[-1] == {"role": "user", "content": "second question"}
    assert "first question" in [message["content"] for message in sent]


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
