"""Chat end to end: retrieve, stream a cited reply, and persist both turns."""

import asyncio
import contextlib
import json
import threading
from collections.abc import AsyncIterator

import pytest
import uvicorn
from httpx import AsyncClient
from sqlalchemy import Engine

from api.main import create_app
from modules.chat.budget import (
    ANSWER_RESERVE_TOKENS,
    EXCERPTS_TOKENS,
    QUESTION_CHARS,
    QUESTION_TOKENS,
    SYSTEM_PROMPT_TOKENS,
)
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.llm.activity import ModelBusyError, model_activity, model_key
from modules.llm.model_type import ModelType
from modules.llm.models import SelectedModel
from modules.workspaces.models import Workspace
from shared.db import create_session_factory
from tests.integration.chat.conftest import (
    REPLY_DELTAS,
    RemoteEndpoint,
    set_answer,
    set_prompt_progress,
    set_props_n_ctx,
    set_props_slots,
    set_reasoning,
    set_tokens_per_word,
    stall_after_answer,
)
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
                model_type=ModelType.TEXT_GEN,
                provider="llamacpp",
                name="Qwen3-1.7B-Q4_K_M",
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
                model_type=ModelType.TEXT_GEN,
                provider="llamacpp",
                name="Qwen3-1.7B-Q4_K_M",
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
    thinking: bool | None = None,
) -> list[dict]:
    events: list[dict] = []
    body: dict = {"text": text}
    if document_ids is not None:
        body["document_ids"] = document_ids
    if thinking is not None:
        body["thinking"] = thinking
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
    assert sent[-1]["role"] == "user"
    assert sent[-1]["content"].endswith("second question")
    assert "first question" in [message["content"] for message in sent]


async def test_a_followup_keeps_the_system_message_and_asks_with_its_own_passages(
    client: AsyncClient, engine: Engine, real_model: object, llamacpp_server: list[dict]
) -> None:
    """llama-server reuses a prompt only up to its first changed token. With the
    passages in the system message, every follow-up re-read its whole history;
    with them in the question, it reads from the previous question on. The
    question is labelled after them: unlabelled, Qwen3 1.7B answered "And the
    X300?" about the X200 its last passage named, in three runs of three."""
    workspace_id, _ids = _seed(engine)
    thread_id = await _open_thread(client, workspace_id)

    await _send(client, thread_id, "what happened to revenue?")
    await _send(client, thread_id, "and after the launch?")

    first, second = (
        request["messages"]
        for request in llamacpp_server
        if request["messages"][0]["role"] == "system"
    )
    assert first[0] == second[0]
    assert FINANCE not in first[0]["content"]
    assert FINANCE in first[-1]["content"]
    assert first[-1]["content"].endswith("\n\nQuestion: what happened to revenue?")
    assert {"role": "user", "content": "what happened to revenue?"} in second
    assert FINANCE in second[-1]["content"]
    assert second[-1]["content"].endswith("\n\nQuestion: and after the launch?")


async def test_a_trimmed_history_starts_where_it_did_on_the_next_turn(
    client: AsyncClient, engine: Engine, real_model: object, llamacpp_server: list[dict]
) -> None:
    """Trimmed to the brim, every turn past the budget moved where the history
    starts, and llama-server re-read all of it. Trimmed with room to spare, the
    next turn starts at the same question."""
    # 40 tokens of history at one token a word: three exchanges fit, a fourth does not.
    fixed = SYSTEM_PROMPT_TOKENS + EXCERPTS_TOKENS + QUESTION_TOKENS
    set_props_n_ctx(fixed + ANSWER_RESERVE_TOKENS + 40)
    set_tokens_per_word(1)
    workspace_id, _ids = _seed(engine)
    thread_id = await _open_thread(client, workspace_id)

    for n in range(6):
        await _send(client, thread_id, f"question number {n} about revenue")

    first_questions = [
        next(m["content"] for m in request["messages"][1:] if m["role"] == "user")
        for request in llamacpp_server
        if request["messages"][0]["role"] == "system"
    ]
    first_cut = next(
        turn for turn, text in enumerate(first_questions) if "number 0" not in text
    )
    assert first_questions[first_cut + 1] == first_questions[first_cut]


async def test_a_thinking_model_shows_its_reasoning_before_the_answer(
    client: AsyncClient, engine: Engine, real_model: object, llamacpp_server: list[dict]
) -> None:
    """The trace streams as its own frames, closes with how long it took, and
    stays with the turn so a reload still shows it."""
    set_reasoning(["The note says ", "revenue climbed."])
    workspace_id, _ids = _seed(engine)
    thread_id = await _open_thread(client, workspace_id)

    events = await _send(client, thread_id, "what happened to revenue?")

    kinds = [event["type"] for event in events]
    trace = [event["text"] for event in events if event["type"] == "reasoning"]
    assert "".join(trace) == "The note says revenue climbed."
    last_trace = max(i for i, kind in enumerate(kinds) if kind == "reasoning")
    assert last_trace < kinds.index("reasoning-end") < kinds.index("delta")
    duration_ms = events[kinds.index("reasoning-end")]["duration_ms"]
    assert isinstance(duration_ms, int) and duration_ms >= 0
    answer = "".join(event["text"] for event in events if event["type"] == "delta")
    assert answer == "Revenue climbed after the launch [1]."

    stored = (await client.get(f"/chat/threads/{thread_id}/messages")).json()
    assert stored[1]["content"]["reasoning"] == {
        "text": "The note says revenue climbed.",
        "duration_ms": duration_ms,
    }


async def test_reading_a_long_prompt_streams_progress_before_the_answer(
    client: AsyncClient, engine: Engine, real_model: object, llamacpp_server: list[dict]
) -> None:
    """The wait before the first token gets a figure that moves: the tokens
    read so far out of those left to read, with the cached prefix taken out.
    It is for the wait only, so it is not stored with the turn."""
    set_prompt_progress(
        [
            {"total": 6144, "cache": 2048, "processed": 2048, "time_ms": 0},
            {"total": 6144, "cache": 2048, "processed": 4096, "time_ms": 300},
            {"total": 6144, "cache": 2048, "processed": 6144, "time_ms": 600},
        ]
    )
    workspace_id, _ids = _seed(engine)
    thread_id = await _open_thread(client, workspace_id)

    events = await _send(client, thread_id, "what happened to revenue?")

    kinds = [event["type"] for event in events]
    progress = [event for event in events if event["type"] == "prompt-progress"]
    assert [(event["processed"], event["total"]) for event in progress] == [
        (0, 4096),
        (2048, 4096),
        (4096, 4096),
    ]
    last = max(i for i, kind in enumerate(kinds) if kind == "prompt-progress")
    assert last < kinds.index("delta")
    answer = "".join(event["text"] for event in events if event["type"] == "delta")
    assert answer == "Revenue climbed after the launch [1]."

    stored = (await client.get(f"/chat/threads/{thread_id}/messages")).json()
    assert stored[1]["content"]["text"].startswith("Revenue climbed")
    assert "progress" not in stored[1]["content"]


async def test_a_reply_with_no_progress_streams_as_it_did(
    client: AsyncClient, engine: Engine, real_model: object, llamacpp_server: list[dict]
) -> None:
    """The frame is optional: an endpoint that reports nothing sends none."""
    workspace_id, _ids = _seed(engine)
    thread_id = await _open_thread(client, workspace_id)

    events = await _send(client, thread_id, "what happened to revenue?")

    assert "prompt-progress" not in {event["type"] for event in events}


async def test_a_turn_sent_with_thinking_off_answers_with_no_trace(
    client: AsyncClient, engine: Engine, real_model: object, llamacpp_server: list[dict]
) -> None:
    """The switch is a field on the turn: the local runtime is told not to
    think, so no trace streams and none is stored."""
    set_reasoning(["The note says ", "revenue climbed."])
    workspace_id, _ids = _seed(engine)
    thread_id = await _open_thread(client, workspace_id)

    events = await _send(client, thread_id, "what happened to revenue?", thinking=False)

    kinds = {event["type"] for event in events}
    assert not kinds & {"reasoning", "reasoning-end"}
    answer = "".join(event["text"] for event in events if event["type"] == "delta")
    assert answer == "Revenue climbed after the launch [1]."
    (asked,) = [r for r in llamacpp_server if r.get("max_tokens") != 12]
    assert asked["thinking_budget_tokens"] == 0
    assert asked["chat_template_kwargs"] == {"enable_thinking": False}

    stored = (await client.get(f"/chat/threads/{thread_id}/messages")).json()
    assert "reasoning" not in stored[1]["content"]


async def test_a_turn_thinks_unless_it_says_otherwise(
    client: AsyncClient, engine: Engine, real_model: object, llamacpp_server: list[dict]
) -> None:
    """Thinking on, sent or left out, adds nothing to the model's request."""
    workspace_id, _ids = _seed(engine)
    thread_id = await _open_thread(client, workspace_id)

    await _send(client, thread_id, "first question")
    await _send(client, thread_id, "second question", thinking=True)

    answers = [r for r in llamacpp_server if r.get("max_tokens") != 12]
    assert len(answers) == 2
    for asked in answers:
        assert "thinking_budget_tokens" not in asked
        assert "chat_template_kwargs" not in asked


async def test_a_followup_never_hands_the_model_its_earlier_reasoning(
    client: AsyncClient, engine: Engine, real_model: object, llamacpp_server: list[dict]
) -> None:
    """A trace is for the person reading it. Sent back, it would spend the next
    turn's window on thinking the model has already done."""
    set_reasoning(["The note says ", "revenue climbed."])
    workspace_id, _ids = _seed(engine)
    thread_id = await _open_thread(client, workspace_id)

    await _send(client, thread_id, "first question")
    llamacpp_server.clear()
    await _send(client, thread_id, "second question")

    sent = [message["content"] for message in llamacpp_server[-1]["messages"]]
    assert not any("revenue climbed." in content for content in sent[1:-1])
    assert "Revenue climbed after the launch" in "".join(sent[1:-1])


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


async def test_a_failed_reply_keeps_the_question_and_its_error(
    client: AsyncClient,
    engine: Engine,
    real_model: object,
    llamacpp_server_unauthorized: None,
) -> None:
    """A failure is classified, not shown raw, and stored with the turn, so a
    window that comes back later still sees why and can retry."""
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
    assert [message["role"] for message in stored] == ["user", "assistant"]
    assert stored[0]["content"]["text"] == "what happened?"
    assert stored[1]["content"]["text"] == ""
    assert stored[1]["content"]["ending"] == {
        "type": "error",
        "kind": "provider_auth",
        "message": error["message"],
    }
    assert stored[1]["completed_at"]
    threads = (await client.get(f"/workspaces/{workspace_id}/chat/threads")).json()
    assert threads[0]["title"] == "New chat"


async def _hang_up_mid_reply(client: AsyncClient, thread_id: int) -> None:
    """Read the whole answer, then close while the model is still generating."""
    deltas: list[str] = []
    async with client.stream(
        "POST",
        f"/chat/threads/{thread_id}/messages",
        json={"text": "how did revenue move?"},
    ) as reply:
        async for line in reply.aiter_lines():
            if line.startswith("data: {"):
                event = json.loads(line[len("data: ") :])
                if event["type"] == "delta":
                    deltas.append(event["text"])
            # By text, not by frame: deltas already waiting arrive as one.
            if "".join(deltas) == "".join(REPLY_DELTAS):
                return


async def _settled_messages(client: AsyncClient, thread_id: int) -> list[dict]:
    """The thread once the server has finished with the abandoned stream."""
    stored: list[dict] = []
    for _ in range(40):
        stored = (await client.get(f"/chat/threads/{thread_id}/messages")).json()
        if len(stored) == 2 and stored[1]["completed_at"]:
            break
        await asyncio.sleep(0.05)
    return stored


async def _model_is_free() -> bool:
    """Whether deleting the chat model would be allowed, as `DELETE /llm/models` asks."""
    for _ in range(40):
        try:
            key = model_key("llamacpp", "Qwen3-1.7B-Q4_K_M")
            async with model_activity.deleting(key):
                return True
        except ModelBusyError:
            await asyncio.sleep(0.05)
    return False


async def test_stopping_a_reply_keeps_its_text_and_frees_the_model(
    live_url: str, engine: Engine, real_model: object, llamacpp_server: list[dict]
) -> None:
    """Stop ends the run where it is: what streamed is stored, marked stopped,
    and the model is free to delete again."""
    release = stall_after_answer()
    workspace_id, _ids = _seed(engine)
    async with AsyncClient(base_url=live_url) as client:
        thread_id = await _open_thread(client, workspace_id)
        await _hang_up_mid_reply(client, thread_id)
        stopped = await client.post(f"/chat/threads/{thread_id}/run/stop")
        stored = await _settled_messages(client, thread_id)
        free = await _model_is_free()
        followed = await client.get(f"/chat/threads/{thread_id}/run")
        release.set()

    assert stopped.status_code == 204
    assert [message["role"] for message in stored] == ["user", "assistant"]
    assert stored[1]["content"]["text"].startswith("Revenue climbed after the launch")
    assert stored[1]["content"]["ending"] == {"type": "stopped"}
    assert free
    assert followed.status_code == 404


async def test_hanging_up_leaves_the_model_in_use(
    live_url: str, engine: Engine, real_model: object, llamacpp_server: list[dict]
) -> None:
    """A window leaving is not a stop: the reply still holds its model."""
    release = stall_after_answer()
    workspace_id, _ids = _seed(engine)
    async with AsyncClient(base_url=live_url) as client:
        thread_id = await _open_thread(client, workspace_id)
        await _hang_up_mid_reply(client, thread_id)
        key = model_key("llamacpp", "Qwen3-1.7B-Q4_K_M")
        with pytest.raises(ModelBusyError):
            async with model_activity.deleting(key):
                pass
        replaying = asyncio.Event()
        following = asyncio.create_task(_follow(client, thread_id, replaying=replaying))
        await replaying.wait()
        release.set()
        await following


async def _follow(
    client: AsyncClient,
    thread_id: int,
    after: int = 0,
    replaying: asyncio.Event | None = None,
) -> tuple[list[dict], list[int]]:
    """Follow a thread's run from `after`: its frames and the ids they carried.

    `replaying` is set once the first frame arrives, so a test can let a
    stalled model finish only after the follower is attached.
    """
    events: list[dict] = []
    ids: list[int] = []
    async with client.stream(
        "GET", f"/chat/threads/{thread_id}/run", params={"after": after}
    ) as reply:
        assert reply.status_code == 200
        async for line in reply.aiter_lines():
            if replaying is not None:
                replaying.set()
            if line.startswith("id: "):
                ids.append(int(line[len("id: ") :]))
            if not line.startswith("data: "):
                continue
            payload = line[len("data: ") :]
            if payload == "[DONE]":
                return events, ids
            events.append(json.loads(payload))
    raise AssertionError("the run's stream must end with the [DONE] sentinel")


async def test_a_reply_keeps_generating_after_its_window_hangs_up(
    live_url: str, engine: Engine, real_model: object, llamacpp_server: list[dict]
) -> None:
    """Leaving a thread drops the follower, never the run: following it again
    replays everything it sent, once, and then the rest."""
    release = stall_after_answer()
    workspace_id, _ids = _seed(engine)
    async with AsyncClient(base_url=live_url) as client:
        thread_id = await _open_thread(client, workspace_id)
        await _hang_up_mid_reply(client, thread_id)
        replaying = asyncio.Event()
        following = asyncio.create_task(_follow(client, thread_id, replaying=replaying))
        await replaying.wait()
        release.set()
        events, ids = await following
        stored = await _settled_messages(client, thread_id)

    assert events[0]["type"] == "accepted"
    assert "".join(e["text"] for e in events if e["type"] == "delta") == "".join(
        REPLY_DELTAS
    )
    assert events[-1]["type"] == "completed"
    assert ids == sorted(set(ids)) and ids[0] == 1
    assert stored[1]["content"]["text"].startswith("Revenue climbed after the launch")
    assert "ending" not in stored[1]["content"]


async def test_the_thread_list_says_which_threads_are_answering(
    live_url: str, engine: Engine, real_model: object, llamacpp_server: list[dict]
) -> None:
    """The Chats dialog marks a thread running from the list alone."""
    release = stall_after_answer()
    workspace_id, _ids = _seed(engine)
    async with AsyncClient(base_url=live_url) as client:
        answering = await _open_thread(client, workspace_id)
        idle = await _open_thread(client, workspace_id)
        await _hang_up_mid_reply(client, answering)
        during = (await client.get(f"/workspaces/{workspace_id}/chat/threads")).json()
        await client.post(f"/chat/threads/{answering}/run/stop")
        after = (await client.get(f"/workspaces/{workspace_id}/chat/threads")).json()
        release.set()

    assert {t["id"]: t["running"] for t in during} == {answering: True, idle: False}
    assert {t["id"]: t["running"] for t in after} == {answering: False, idle: False}


async def test_a_run_starting_and_ending_reaches_open_windows(
    live_url: str, engine: Engine, real_model: object, llamacpp_server: list[dict]
) -> None:
    """Every window learns a thread started or stopped answering, as it learns
    a document changed."""
    workspace_id, _ids = _seed(engine)
    notices: list[tuple[str, dict]] = []
    async with AsyncClient(base_url=live_url, timeout=10) as client:
        thread_id = await _open_thread(client, workspace_id)
        async with client.stream("GET", f"/workspaces/{workspace_id}/events") as events:
            lines = events.aiter_lines()
            async for line in lines:
                if line.startswith(": connected"):
                    break
            await _send(client, thread_id, "how did revenue move?")
            name = ""
            async for line in lines:
                if line.startswith("event: "):
                    name = line.removeprefix("event: ")
                elif line.startswith("data: ") and name == "chat-runs":
                    notices.append((name, json.loads(line.removeprefix("data: "))))
                    if len(notices) == 2:
                        break

    assert notices == [
        ("chat-runs", {"ids": [thread_id], "status": "running"}),
        ("chat-runs", {"ids": [thread_id], "status": "done"}),
    ]


async def test_a_thread_answers_one_message_at_a_time(
    live_url: str, engine: Engine, real_model: object, llamacpp_server: list[dict]
) -> None:
    """A second message while the first is answering would interleave two replies."""
    release = stall_after_answer()
    workspace_id, _ids = _seed(engine)
    async with AsyncClient(base_url=live_url) as client:
        thread_id = await _open_thread(client, workspace_id)
        await _hang_up_mid_reply(client, thread_id)
        second = await client.post(
            f"/chat/threads/{thread_id}/messages", json={"text": "and costs?"}
        )
        await client.post(f"/chat/threads/{thread_id}/run/stop")
        release.set()
        stored = await _settled_messages(client, thread_id)

    assert second.status_code == 409
    assert [message["role"] for message in stored] == ["user", "assistant"]


async def test_deleting_a_thread_stops_its_reply_first(
    live_url: str, engine: Engine, real_model: object, llamacpp_server: list[dict]
) -> None:
    """A reply left running would go on writing into a thread that is gone."""
    release = stall_after_answer()
    workspace_id, _ids = _seed(engine)
    async with AsyncClient(base_url=live_url) as client:
        thread_id = await _open_thread(client, workspace_id)
        await _hang_up_mid_reply(client, thread_id)
        deleted = await client.delete(f"/chat/threads/{thread_id}")
        active = (await client.get("/chat/runs")).json()["active"]
        followed = await client.get(f"/chat/threads/{thread_id}/run")
        free = await _model_is_free()
        release.set()

    assert deleted.status_code == 204
    assert active == 0
    assert followed.status_code == 404
    assert free


async def test_deleting_a_workspace_stops_its_replies_first(
    live_url: str, engine: Engine, real_model: object, llamacpp_server: list[dict]
) -> None:
    """Every thread in the workspace goes with it, so none may still be writing."""
    release = stall_after_answer()
    workspace_id, _ids = _seed(engine)
    async with AsyncClient(base_url=live_url) as client:
        thread_id = await _open_thread(client, workspace_id)
        await _hang_up_mid_reply(client, thread_id)
        deleted = await client.delete(f"/workspaces/{workspace_id}")
        active = (await client.get("/chat/runs")).json()["active"]
        release.set()

    assert deleted.status_code == 204
    assert active == 0


@pytest.mark.parametrize("reasoning", [[], ["The note says ", "nothing useful."]])
async def test_a_reply_with_no_text_is_kept_as_failed(
    client: AsyncClient,
    engine: Engine,
    real_model: object,
    llamacpp_server: list[dict],
    reasoning: list[str],
) -> None:
    """A stream that closes cleanly with no answer, even after thinking, is a
    failure the person can see and retry, not a vanished question."""
    set_reasoning(reasoning)
    set_answer([])
    workspace_id, _ids = _seed(engine)
    thread_id = await _open_thread(client, workspace_id)

    events = await _send(client, thread_id, "what happened?")

    error = next(event for event in events if event["type"] == "error")
    assert error["kind"] == "unknown"
    assert not any(event["type"] == "completed" for event in events)

    stored = (await client.get(f"/chat/threads/{thread_id}/messages")).json()
    assert [message["role"] for message in stored] == ["user", "assistant"]
    assert stored[1]["content"]["ending"]["type"] == "error"
    assert stored[1]["content"]["ending"]["kind"] == "unknown"
    threads = (await client.get(f"/workspaces/{workspace_id}/chat/threads")).json()
    assert threads[0]["title"] == "New chat"


async def test_retrying_a_failed_turn_replaces_it(
    client: AsyncClient, engine: Engine, real_model: object, llamacpp_server: list[dict]
) -> None:
    """Retry asks again in place: the question appears once, with the new reply."""
    set_answer([])
    workspace_id, _ids = _seed(engine)
    thread_id = await _open_thread(client, workspace_id)
    await _send(client, thread_id, "how did revenue move?")
    failed = (await client.get(f"/chat/threads/{thread_id}/messages")).json()

    set_answer(list(REPLY_DELTAS))
    events: list[dict] = []
    async with client.stream(
        "POST",
        f"/chat/threads/{thread_id}/messages",
        json={"text": "how did revenue move?", "retry_of": failed[1]["id"]},
    ) as reply:
        assert reply.status_code == 200
        async for line in reply.aiter_lines():
            if line.startswith("data: {"):
                events.append(json.loads(line[len("data: ") :]))
    stored = (await client.get(f"/chat/threads/{thread_id}/messages")).json()

    assert [m["content"]["text"] for m in stored] == [
        "how did revenue move?",
        stored[1]["content"]["text"],
    ]
    assert stored[1]["content"]["text"].startswith("Revenue climbed after the launch")
    assert {m["id"] for m in stored}.isdisjoint({m["id"] for m in failed})
    assert events[-1]["type"] == "completed"


async def test_only_the_latest_failed_turn_can_be_retried(
    client: AsyncClient, engine: Engine, real_model: object, llamacpp_server: list[dict]
) -> None:
    """An older failure stays as a record; a reply that worked is not a retry."""
    set_answer([])
    workspace_id, _ids = _seed(engine)
    thread_id = await _open_thread(client, workspace_id)
    await _send(client, thread_id, "first?")
    set_answer(list(REPLY_DELTAS))
    await _send(client, thread_id, "second?")
    stored = (await client.get(f"/chat/threads/{thread_id}/messages")).json()

    older_failure = await client.post(
        f"/chat/threads/{thread_id}/messages",
        json={"text": "first?", "retry_of": stored[1]["id"]},
    )
    a_success = await client.post(
        f"/chat/threads/{thread_id}/messages",
        json={"text": "second?", "retry_of": stored[3]["id"]},
    )

    assert older_failure.status_code == 409
    assert a_success.status_code == 409
    assert len((await client.get(f"/chat/threads/{thread_id}/messages")).json()) == 4


async def test_stopping_before_any_text_leaves_no_trace(
    live_url: str, engine: Engine, real_model: object, llamacpp_server: list[dict]
) -> None:
    """The person chose to stop and nothing was written: there is nothing to keep."""
    set_answer([])
    release = stall_after_answer()
    workspace_id, _ids = _seed(engine)
    async with AsyncClient(base_url=live_url) as client:
        thread_id = await _open_thread(client, workspace_id)
        async with client.stream(
            "POST", f"/chat/threads/{thread_id}/messages", json={"text": "hi"}
        ) as reply:
            async for line in reply.aiter_lines():
                if line.startswith("data: {") and '"accepted"' in line:
                    break
        stopped = await client.post(f"/chat/threads/{thread_id}/run/stop")
        stored = (await client.get(f"/chat/threads/{thread_id}/messages")).json()
        release.set()

    assert stopped.status_code == 204
    assert stored == []


async def test_a_curated_model_answers_at_its_publishers_sampling(
    client: AsyncClient,
    engine: Engine,
    real_model: object,
    llamacpp_server: list[dict],
) -> None:
    """Qwen3's entry commits its thinking set; the title keeps its own zero."""
    workspace_id, _ids = _seed(engine)
    thread_id = await _open_thread(client, workspace_id)

    await _send(client, thread_id, "how did revenue move?")

    title, answer = sorted(llamacpp_server, key=lambda r: r.get("max_tokens") != 12)
    assert title["temperature"] == 0
    assert answer["temperature"] == 0.6
    assert (answer["top_p"], answer["top_k"], answer["min_p"]) == (0.95, 20, 0.0)


async def test_a_thread_with_no_model_selected_is_a_409(client: AsyncClient) -> None:
    """Refused before retrieval, so the frontend can route the user to setup."""
    workspace = (await client.post("/workspaces", json={"name": "w"})).json()
    thread_id = await _open_thread(client, workspace["id"])

    reply = await client.post(
        f"/chat/threads/{thread_id}/messages", json={"text": "hi"}
    )

    assert reply.status_code == 409


async def test_a_question_past_its_share_is_refused_at_the_wire(
    client: AsyncClient,
) -> None:
    """Refused before a model is resolved or retrieval runs: with no model
    selected, a message that got past the schema would be the 409 above."""
    workspace = (await client.post("/workspaces", json={"name": "w"})).json()
    thread_id = await _open_thread(client, workspace["id"])

    reply = await client.post(
        f"/chat/threads/{thread_id}/messages",
        json={"text": "x" * (QUESTION_CHARS + 1)},
    )

    assert reply.status_code == 422


async def test_missing_embedding_assets_are_an_actionable_503(
    client: AsyncClient, engine: Engine
) -> None:
    """A dev setup omission is reported before retrieval crashes with a generic 500."""
    with create_session_factory(engine)() as session:
        session.add(
            SelectedModel(
                model_type=ModelType.TEXT_GEN,
                provider="llamacpp",
                name="Qwen3-1.7B-Q4_K_M",
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


async def test_chat_before_an_embedder_is_chosen_is_a_409(
    unlocked_client: AsyncClient, unlocked_engine: Engine
) -> None:
    """The API reached before onboarding finishes: say why, rather than guess a model."""
    with create_session_factory(unlocked_engine)() as session:
        session.add(
            SelectedModel(
                model_type=ModelType.TEXT_GEN,
                provider="llamacpp",
                name="Qwen3-1.7B-Q4_K_M",
            )
        )
        session.commit()
    workspace = (await unlocked_client.post("/workspaces", json={"name": "w"})).json()
    thread_id = await _open_thread(unlocked_client, workspace["id"])

    reply = await unlocked_client.post(
        f"/chat/threads/{thread_id}/messages", json={"text": "hi"}
    )

    assert reply.status_code == 409
    assert reply.json()["detail"]["code"] == "embedding_not_chosen"


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


def _seed_for_remote(engine: Engine) -> int:
    """A workspace of one ingested note; the remote fixture picks the model."""
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
        session.commit()
        workspace_id, doc_id = workspace.id, doc.id
    run(doc_id)
    return workspace_id


async def test_a_remote_reply_keeps_generating_after_its_window_hangs_up(
    live_url: str, engine: Engine, real_model: object, remote_endpoint: RemoteEndpoint
) -> None:
    """A remote model gets the same run: the window leaves, the reply goes on."""
    remote_endpoint.stall = threading.Event()
    workspace_id = _seed_for_remote(engine)
    async with AsyncClient(base_url=live_url) as client:
        thread_id = await _open_thread(client, workspace_id)
        await _hang_up_mid_reply(client, thread_id)
        replaying = asyncio.Event()
        following = asyncio.create_task(_follow(client, thread_id, replaying=replaying))
        await replaying.wait()
        remote_endpoint.stall.set()
        events, _ids = await following
        stored = await _settled_messages(client, thread_id)

    assert events[-1]["type"] == "completed"
    assert stored[1]["content"]["text"].startswith("Revenue climbed after the launch")


async def test_a_remote_rate_limit_is_kept_with_the_turn(
    client: AsyncClient,
    engine: Engine,
    real_model: object,
    remote_endpoint: RemoteEndpoint,
) -> None:
    """A provider's 429 ends the run as `provider_rate_limited`, question kept."""
    remote_endpoint.status = 429
    workspace_id = _seed_for_remote(engine)
    thread_id = await _open_thread(client, workspace_id)

    await _send(client, thread_id, "how did revenue move?")
    stored = (await client.get(f"/chat/threads/{thread_id}/messages")).json()

    assert stored[0]["content"]["text"] == "how did revenue move?"
    assert stored[1]["content"]["ending"]["kind"] == "provider_rate_limited"


async def test_two_threads_answer_at_once_on_one_remote_connection(
    live_url: str, engine: Engine, real_model: object, remote_endpoint: RemoteEndpoint
) -> None:
    """Nothing queues a remote model: two replies stream side by side."""
    remote_endpoint.stall = threading.Event()
    workspace_id = _seed_for_remote(engine)
    async with AsyncClient(base_url=live_url) as client:
        first = await _open_thread(client, workspace_id)
        second = await _open_thread(client, workspace_id)
        await _hang_up_mid_reply(client, first)
        await _hang_up_mid_reply(client, second)
        listed = (await client.get(f"/workspaces/{workspace_id}/chat/threads")).json()
        most_open = remote_endpoint.most_open
        remote_endpoint.stall.set()
        for thread_id in (first, second):
            await _settled_messages(client, thread_id)

    assert most_open == 2
    assert all(thread["running"] for thread in listed)


async def test_quitting_saves_every_reply_as_interrupted(
    live_url: str, engine: Engine, real_model: object, llamacpp_server: list[dict]
) -> None:
    """Before the app closes, every run stores what it has, marked as cut off by
    the quit rather than stopped by the person, and keeps its question."""
    set_props_slots(2)
    release = stall_after_answer()
    workspace_id, _ids = _seed(engine)
    async with AsyncClient(base_url=live_url) as client:
        first = await _open_thread(client, workspace_id)
        second = await _open_thread(client, workspace_id)
        await _hang_up_mid_reply(client, first)
        await _hang_up_mid_reply(client, second)
        before = (await client.get("/chat/runs")).json()
        stopped = await client.post("/chat/runs/stop-all")
        after = (await client.get("/chat/runs")).json()
        stored = [
            (await client.get(f"/chat/threads/{thread}/messages")).json()
            for thread in (first, second)
        ]
        release.set()

    assert before == {"active": 2}
    assert stopped.status_code == 204
    assert after == {"active": 0}
    for turns in stored:
        assert turns[1]["content"]["text"].startswith("Revenue climbed")
        assert turns[1]["content"]["ending"] == {"type": "interrupted"}
        assert turns[1]["completed_at"]


async def test_a_reply_cut_off_by_a_crash_is_settled_when_the_app_starts(
    engine: Engine,
) -> None:
    """A crash leaves replies with no end; the next start marks them interrupted,
    text or not, so none looks finished and no question goes missing."""
    from modules.chat.models import ChatMessage, ChatThread, MessageRole

    # Seeded straight into the database the next boot reads, as a crash leaves it.
    with create_session_factory(engine)() as session:
        workspace = Workspace(name="w")
        session.add(workspace)
        session.flush()
        thread = ChatThread(workspace_id=workspace.id, title="t")
        session.add(thread)
        session.flush()
        for question, partial in (("first?", "Revenue cl"), ("second?", "")):
            session.add(
                ChatMessage(
                    chat_thread_id=thread.id,
                    role=MessageRole.USER,
                    content={"text": question},
                )
            )
            session.add(
                ChatMessage(
                    chat_thread_id=thread.id,
                    role=MessageRole.ASSISTANT,
                    content={"text": partial, "citations": []},
                )
            )
        session.commit()
        thread_id = thread.id

    # Booted only now, so its startup finds what the crash left.
    async with _booted_app() as url, AsyncClient(base_url=url) as client:
        stored = (await client.get(f"/chat/threads/{thread_id}/messages")).json()

    replies = [m for m in stored if m["role"] == "assistant"]
    assert [m["content"]["text"] for m in replies] == ["Revenue cl", ""]
    assert all(m["content"]["ending"] == {"type": "interrupted"} for m in replies)
    assert all(m["completed_at"] for m in replies)
    assert len(stored) == 4


@contextlib.asynccontextmanager
async def _booted_app() -> AsyncIterator[str]:
    """The app on a real port with its startup run, over this test's database."""
    server = uvicorn.Server(
        uvicorn.Config(create_app(), host="127.0.0.1", port=0, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        while not server.started:
            await asyncio.sleep(0.01)
        yield f"http://127.0.0.1:{server.servers[0].sockets[0].getsockname()[1]}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)


async def test_a_running_reply_saves_its_text_as_it_goes(
    live_url: str,
    engine: Engine,
    real_model: object,
    llamacpp_server: list[dict],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A crash mid-reply loses at most the last few seconds: the text written so
    far is already stored, with citations resolved as at the end."""
    monkeypatch.setattr("modules.chat.runs.live_text.SAVE_EVERY_SECONDS", 0.05)
    release = stall_after_answer()
    workspace_id, _ids = _seed(engine)
    async with AsyncClient(base_url=live_url) as client:
        thread_id = await _open_thread(client, workspace_id)
        await _hang_up_mid_reply(client, thread_id)
        saved: dict = {}
        for _ in range(100):
            stored = (await client.get(f"/chat/threads/{thread_id}/messages")).json()
            if stored[1]["content"]["text"]:
                saved = stored[1]
                break
            await asyncio.sleep(0.02)
        release.set()
        await _settled_messages(client, thread_id)

    assert saved["content"]["text"].startswith("Revenue climbed after the launch")
    assert "[1]" not in saved["content"]["text"]
    assert saved["completed_at"] is None


async def test_a_local_reply_waits_its_turn_and_says_so(
    live_url: str, engine: Engine, real_model: object, llamacpp_server: list[dict]
) -> None:
    """One slot: the second thread queues, says where it stands, then answers
    once the first is done, instead of hanging on an unexplained "Thinking"."""
    set_props_slots(1)
    release = stall_after_answer()
    workspace_id, _ids = _seed(engine)
    async with AsyncClient(base_url=live_url) as client:
        first = await _open_thread(client, workspace_id)
        second = await _open_thread(client, workspace_id)
        await _hang_up_mid_reply(client, first)
        queued: list[dict] = []
        async with client.stream(
            "POST", f"/chat/threads/{second}/messages", json={"text": "and costs?"}
        ) as reply:
            async for line in reply.aiter_lines():
                if line.startswith("data: {"):
                    event = json.loads(line[len("data: ") :])
                    if event["type"] == "run-state":
                        queued.append(event)
                        break
        replaying = asyncio.Event()
        following = asyncio.create_task(_follow(client, second, replaying=replaying))
        await replaying.wait()
        release.set()
        events, _ids2 = await following

    assert queued == [{"type": "run-state", "state": "queued", "position": 1}]
    states = [e for e in events if e["type"] == "run-state"]
    assert states[-1] == {"type": "run-state", "state": "running"}
    assert events[-1]["type"] == "completed"


async def test_the_thread_list_says_where_each_reply_stands(
    live_url: str, engine: Engine, real_model: object, llamacpp_server: list[dict]
) -> None:
    """A window that follows neither reply still sees which one waits, and where."""
    set_props_slots(1)
    release = stall_after_answer()
    workspace_id, _ids = _seed(engine)
    async with AsyncClient(base_url=live_url) as client:
        first = await _open_thread(client, workspace_id)
        second = await _open_thread(client, workspace_id)
        idle = await _open_thread(client, workspace_id)
        await _hang_up_mid_reply(client, first)
        async with client.stream(
            "POST", f"/chat/threads/{second}/messages", json={"text": "and costs?"}
        ) as reply:
            async for line in reply.aiter_lines():
                if line.startswith("data: {") and '"run-state"' in line:
                    break
        listed = (await client.get(f"/workspaces/{workspace_id}/chat/threads")).json()
        release.set()
        for thread_id in (first, second):
            await _settled_messages(client, thread_id)

    assert {t["id"]: t["run_state"] for t in listed} == {
        first: {"state": "running", "position": None},
        second: {"state": "queued", "position": 1},
        idle: None,
    }


async def test_two_local_replies_generate_together_when_the_runtime_has_two_slots(
    live_url: str, engine: Engine, real_model: object, llamacpp_server: list[dict]
) -> None:
    """With room for both, neither waits: two threads stream side by side."""
    set_props_slots(2)
    release = stall_after_answer()
    workspace_id, _ids = _seed(engine)
    async with AsyncClient(base_url=live_url) as client:
        first = await _open_thread(client, workspace_id)
        second = await _open_thread(client, workspace_id)
        await _hang_up_mid_reply(client, first)
        await _hang_up_mid_reply(client, second)
        listed = (await client.get(f"/workspaces/{workspace_id}/chat/threads")).json()
        release.set()
        for thread_id in (first, second):
            await _settled_messages(client, thread_id)

    assert all(thread["running"] for thread in listed)
