"""Chat end to end: retrieve, stream a cited reply, and persist both turns."""

import json

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine

from modules.chat.budget import ANSWER_RESERVE_TOKENS
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.llm.models import ModelRole, SelectedModel
from modules.workspaces.models import Workspace
from shared.db import create_session_factory
from tests.integration.chat.conftest import set_props_n_ctx, set_tokens_per_word
from worker.ingestion import run

pytestmark = pytest.mark.integration

FINANCE = "Quarterly revenue climbed after the spring product launch."
CAT = "The feline dozed on the warm windowsill."


def _seed(
    engine: Engine, notes: dict[str, str] | None = None
) -> tuple[int, dict[str, int]]:
    """A workspace of ingested notes and a chosen chat model."""
    notes = notes or {"note": FINANCE}
    with create_session_factory(engine)() as session:
        workspace = Workspace(name="Notes")
        session.add(workspace)
        session.flush()
        ids: dict[str, int] = {}
        for title, content in notes.items():
            doc = Document(
                workspace_id=workspace.id,
                title=title,
                document_type=DocumentType.NOTE,
                content=content,
            )
            session.add(doc)
            session.flush()
            ids[title] = doc.id
        session.add(
            SelectedModel(
                role=ModelRole.GENERATION, provider="llamacpp", name="Qwen3-1.7B-Q4_K_M"
            )
        )
        session.commit()
        workspace_id = workspace.id

    for doc_id in ids.values():
        run(doc_id)
    return workspace_id, ids


def _choose_generation_model(engine: Engine) -> None:
    with create_session_factory(engine)() as session:
        session.add(
            SelectedModel(
                role=ModelRole.GENERATION, provider="llamacpp", name="Qwen3-1.7B-Q4_K_M"
            )
        )
        session.commit()


async def _open_thread(client: AsyncClient, workspace_id: int) -> int:
    reply = await client.post(f"/workspaces/{workspace_id}/chat/threads", json={})
    return reply.json()["id"]


async def _send(
    client: AsyncClient,
    thread_id: int,
    text: str,
    document_ids: list[int] | None = None,
) -> list[dict]:
    events: list[dict] = []
    body: dict = {"text": text}
    if document_ids is not None:
        body["document_ids"] = document_ids
    async with client.stream(
        "POST", f"/chat/threads/{thread_id}/messages", json=body
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
    client: AsyncClient, engine: Engine, real_model: object, llamacpp_server: list[dict]
) -> None:
    """Deltas arrive, the citation tail names the source doc, both turns persist."""
    workspace_id, ids = _seed(engine)
    doc_id = ids["note"]
    thread_id = await _open_thread(client, workspace_id)

    events = await _send(client, thread_id, "what happened to revenue?")

    accepted = events[0]
    assert accepted["type"] == "accepted"
    assert accepted["user_message_id"] > 0
    assert accepted["assistant_message_id"] > 0
    assert accepted["user_created_at"]

    catalog = events[1]
    assert catalog["type"] == "citation-catalog"
    assert len(catalog["items"]) == 1
    assert catalog["items"][0]["source_id"] == 1
    assert catalog["items"][0]["document_id"] == doc_id
    assert catalog["items"][0]["title"] == "note"
    chunk_id = catalog["items"][0]["chunk_id"]

    title = events[2]
    assert title == {"type": "thread-title-update", "title": "Revenue Growth"}
    assert (
        next(event["type"] for event in events if event["type"] == "delta") == "delta"
    )

    deltas = [event["text"] for event in events if event["type"] == "delta"]
    assert "".join(deltas) == "Revenue climbed after the launch [1]."

    citations = next(event for event in events if event["type"] == "citations")
    assert any(cite["document_id"] == doc_id for cite in citations["items"])
    assert citations["items"][0]["source_id"] == 1
    completed = next(event for event in events if event["type"] == "completed")
    assert completed["assistant_completed_at"]
    assert (
        completed["text"] == f"Revenue climbed after the launch [citation:{chunk_id}]."
    )

    stored = (await client.get(f"/chat/threads/{thread_id}/messages")).json()
    assert [message["role"] for message in stored] == ["user", "assistant"]
    assert [message["id"] for message in stored] == [
        accepted["user_message_id"],
        accepted["assistant_message_id"],
    ]
    assert stored[1]["content"]["text"] == completed["text"]
    assert stored[1]["content"]["citations"]
    assert stored[0]["completed_at"] is None
    assert stored[1]["completed_at"] == completed["assistant_completed_at"]
    threads = (await client.get(f"/workspaces/{workspace_id}/chat/threads")).json()
    assert threads[0]["title"] == "Revenue Growth"
    # The window is fixed at load now, not sized per request: llama.cpp takes
    # `-c` once when the model is loaded, so there is no per-call equivalent of
    # `num_ctx` to assert here.
    assert llamacpp_server[0]["max_tokens"] == 12
    assert llamacpp_server[0]["temperature"] == 0
    assert llamacpp_server[0]["stream"] is True


async def test_a_message_retrieves_only_from_selected_sources(
    client: AsyncClient, engine: Engine, real_model: object, llamacpp_server: list[dict]
) -> None:
    """document_ids is the RAG scope: an unselected source cannot be cited."""
    workspace_id, ids = _seed(engine, {"finance": FINANCE, "cat": CAT})
    thread_id = await _open_thread(client, workspace_id)

    events = await _send(
        client,
        thread_id,
        "what happened to revenue?",
        document_ids=[ids["cat"]],
    )

    catalog = next(event for event in events if event["type"] == "citation-catalog")
    assert catalog["items"]
    assert {item["document_id"] for item in catalog["items"]} == {ids["cat"]}


async def test_a_message_rejects_a_source_from_another_workspace(
    client: AsyncClient, engine: Engine
) -> None:
    """A selected id must belong to this thread's workspace."""
    _choose_generation_model(engine)
    workspace = (await client.post("/workspaces", json={"name": "Mine"})).json()
    other = (await client.post("/workspaces", json={"name": "Other"})).json()
    with create_session_factory(engine)() as session:
        foreign = Document(
            workspace_id=other["id"],
            title="foreign",
            document_type=DocumentType.NOTE,
            status=DocumentStatus.READY,
            content="x",
        )
        session.add(foreign)
        session.commit()
        foreign_id = foreign.id
    thread_id = await _open_thread(client, workspace["id"])

    reply = await client.post(
        f"/chat/threads/{thread_id}/messages",
        json={"text": "hi", "document_ids": [foreign_id]},
    )

    assert reply.status_code == 422


async def test_a_message_waits_for_a_source_to_index(
    client: AsyncClient, engine: Engine
) -> None:
    """A pending note is not searchable yet, so it cannot ground a turn."""
    _choose_generation_model(engine)
    workspace = (await client.post("/workspaces", json={"name": "w"})).json()
    note = await client.post(
        f"/workspaces/{workspace['id']}/documents",
        json={"title": "Draft", "content": "unindexed"},
    )
    thread_id = await _open_thread(client, workspace["id"])

    reply = await client.post(
        f"/chat/threads/{thread_id}/messages",
        json={"text": "hi", "document_ids": [int(note.json()["id"])]},
    )

    assert reply.status_code == 409


async def test_a_followup_carries_the_earlier_turn(
    client: AsyncClient, engine: Engine, real_model: object, llamacpp_server: list[dict]
) -> None:
    """The second message hands the model the first turn as history."""
    workspace_id, _ids = _seed(engine)
    thread_id = await _open_thread(client, workspace_id)

    await _send(client, thread_id, "first question")
    llamacpp_server.clear()
    await _send(client, thread_id, "second question")

    assert len(llamacpp_server) == 1
    sent = llamacpp_server[-1]["messages"]
    assert sent[0]["role"] == "system"
    assert sent[-1] == {"role": "user", "content": "second question"}
    assert "first question" in [message["content"] for message in sent]


async def test_title_failure_does_not_block_the_answer(
    client: AsyncClient,
    engine: Engine,
    real_model: object,
    llamacpp_server: list[dict],
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
        == "Revenue climbed after the launch [1]."
    )
    threads = (await client.get(f"/workspaces/{workspace_id}/chat/threads")).json()
    assert threads[0]["title"] == "New chat"


async def test_a_failed_reply_is_classified_and_leaves_no_trace(
    client: AsyncClient,
    engine: Engine,
    real_model: object,
    llamacpp_server_unauthorized: None,
) -> None:
    """A generation failure is classified, not shown raw, and the turn is discarded."""
    workspace_id, _ids = _seed(engine)
    thread_id = await _open_thread(client, workspace_id)

    events = await _send(client, thread_id, "what happened?")

    error = next(event for event in events if event["type"] == "error")
    assert error["kind"] == "provider_auth"
    assert "HTTPStatusError" not in error["message"]
    assert "401" not in error["message"]
    assert not any(event["type"] == "completed" for event in events)
    assert not any(event["type"] == "thread-title-update" for event in events)

    stored = (await client.get(f"/chat/threads/{thread_id}/messages")).json()
    assert stored == []
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
                role=ModelRole.GENERATION, provider="llamacpp", name="Qwen3-1.7B-Q4_K_M"
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


async def test_the_answer_reserves_room_instead_of_taking_the_whole_window(
    client: AsyncClient, engine: Engine, real_model: object, llamacpp_server: list[dict]
) -> None:
    """A model whose window is known gets a capped answer request, so a long
    reply stops cleanly instead of being cut off mid-sentence by the window
    running out with no `max_tokens` set at all."""
    set_props_n_ctx(16384)
    workspace_id, _ = _seed(engine)
    thread_id = await _open_thread(client, workspace_id)

    await _send(client, thread_id, "what happened to revenue?")

    answer_requests = [r for r in llamacpp_server if r.get("max_tokens") != 12]
    assert answer_requests
    assert answer_requests[-1]["max_tokens"] == ANSWER_RESERVE_TOKENS


async def test_history_is_trimmed_by_the_models_own_tokenizer_when_it_answers(
    client: AsyncClient, engine: Engine, real_model: object, llamacpp_server: list[dict]
) -> None:
    """The exact count reaches the wire, not just the unit tests: an early
    turn a permissive heuristic would have kept is dropped once the stub's
    `/tokenize` prices it heavily, and the turn nearer the question survives."""
    set_tokens_per_word(1000)  # any one turn alone blows the whole history budget
    workspace_id, _ = _seed(engine)
    thread_id = await _open_thread(client, workspace_id)

    await _send(client, thread_id, "first turn establishing some history")
    await _send(client, thread_id, "what happened to revenue?")

    answer_requests = [r for r in llamacpp_server if r.get("max_tokens") != 12]
    assert answer_requests
    roles = [m["role"] for m in answer_requests[-1]["messages"]]
    # System and the new question always survive; the expensive first turn
    # does not, because the exact count priced it out of the budget.
    assert roles == ["system", "user"]
