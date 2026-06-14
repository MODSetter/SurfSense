"""respx-mocked tests for the SurfSense HTTP clients."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from surfsense_evals.core.clients import (
    DocumentsClient,
    NewChatClient,
    SearchSpaceClient,
)
from surfsense_evals.core.clients.new_chat import ThreadBusyError

_BASE = "http://test"


@pytest.fixture
def http() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=_BASE)


# ---------------------------------------------------------------------------
# SearchSpaceClient
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_create_search_space_returns_row(respx_mock, http):
    respx_mock.post("/api/v1/searchspaces").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": 99,
                "name": "eval-medical-2026",
                "description": None,
                "user_id": "user-x",
                "citations_enabled": True,
                "qna_custom_instructions": None,
            },
        )
    )
    client = SearchSpaceClient(http, _BASE)
    row = await client.create("eval-medical-2026")
    assert row.id == 99
    assert row.name == "eval-medical-2026"


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_delete_search_space_idempotent_on_404(respx_mock, http):
    respx_mock.delete("/api/v1/searchspaces/42").mock(
        return_value=httpx.Response(404, json={"detail": "gone"})
    )
    client = SearchSpaceClient(http, _BASE)
    await client.delete(42)  # must not raise


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_set_model_roles_partial_update(respx_mock, http):
    route = respx_mock.put("/api/v1/search-spaces/42/model-roles").mock(
        return_value=httpx.Response(
            200,
            json={
                "chat_model_id": -10042,
                "image_gen_model_id": None,
                "vision_model_id": None,
            },
        )
    )
    client = SearchSpaceClient(http, _BASE)
    roles = await client.set_model_roles(42, chat_model_id=-10042)
    assert roles.chat_model_id == -10042
    sent_body = json.loads(route.calls[-1].request.content)
    assert sent_body == {"chat_model_id": -10042}


# ---------------------------------------------------------------------------
# DocumentsClient
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_documents_status_parses_state(respx_mock, http):
    respx_mock.get("/api/v1/documents/status").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {"id": 1, "title": "a.pdf", "document_type": "FILE",
                     "status": {"state": "ready", "reason": None}},
                    {"id": 2, "title": "b.pdf", "document_type": "FILE",
                     "status": {"state": "failed", "reason": "ETL boom"}},
                ]
            },
        )
    )
    client = DocumentsClient(http, _BASE)
    statuses = await client.get_status(search_space_id=1, document_ids=[1, 2])
    assert {s.document_id for s in statuses} == {1, 2}
    assert {s.is_ready for s in statuses} == {True, False}


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_documents_upload_returns_payload(respx_mock, http, tmp_path: Path):
    f1 = tmp_path / "a.pdf"
    f1.write_bytes(b"%PDF-1.4 small")
    respx_mock.post("/api/v1/documents/fileupload").mock(
        return_value=httpx.Response(
            200,
            json={
                "message": "Files uploaded",
                "document_ids": [101],
                "duplicate_document_ids": [],
                "total_files": 1,
                "pending_files": 1,
                "skipped_duplicates": 0,
            },
        )
    )
    client = DocumentsClient(http, _BASE)
    result = await client.upload(files=[f1], search_space_id=7)
    assert result.document_ids == [101]
    assert result.pending_files == 1


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_documents_list_chunks_paginated(respx_mock, http):
    respx_mock.get("/api/v1/documents/5/chunks").mock(
        side_effect=[
            httpx.Response(200, json={
                "items": [{"id": 1, "content": "a"}, {"id": 2, "content": "b"}],
                "total": 3, "page": 0, "page_size": 2, "has_more": True,
            }),
            httpx.Response(200, json={
                "items": [{"id": 3, "content": "c"}],
                "total": 3, "page": 1, "page_size": 2, "has_more": False,
            }),
        ]
    )
    client = DocumentsClient(http, _BASE)
    rows = await client.list_chunks(5, page_size=2)
    assert [r.id for r in rows] == [1, 2, 3]


# ---------------------------------------------------------------------------
# NewChatClient
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_create_thread_returns_id(respx_mock, http):
    respx_mock.post("/api/v1/threads").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": 555,
                "title": "eval",
                "archived": False,
                "visibility": "PRIVATE",
                "search_space_id": 1,
                "messages": [],
                "created_at": "2026-05-11T00:00:00Z",
                "updated_at": "2026-05-11T00:00:00Z",
            },
        )
    )
    client = NewChatClient(http, _BASE)
    tid = await client.create_thread(search_space_id=1)
    assert tid == 555


def _sse_body(events: list[dict]) -> bytes:
    parts = []
    for ev in events:
        parts.append(f"data: {json.dumps(ev)}\n\n")
    parts.append("data: [DONE]\n\n")
    return "".join(parts).encode("utf-8")


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_ask_accumulates_text_deltas(respx_mock, http):
    body = _sse_body([
        {"type": "start", "messageId": "m1"},
        {"type": "text-start", "id": "t1"},
        {"type": "text-delta", "id": "t1", "delta": "Answer "},
        {"type": "text-delta", "id": "t1", "delta": "is "},
        {"type": "text-delta", "id": "t1", "delta": "B [citation:42]."},
        {"type": "text-end", "id": "t1"},
        {"type": "finish"},
    ])
    respx_mock.post("/api/v1/new_chat").mock(
        return_value=httpx.Response(
            200,
            content=body,
            headers={"Content-Type": "text/event-stream"},
        )
    )
    client = NewChatClient(http, _BASE)
    answer = await client.ask(
        thread_id=1, search_space_id=2, user_query="What is the answer?"
    )
    assert answer.text == "Answer is B [citation:42]."
    assert answer.finished_normally is True
    assert any(c["chunk_id"] == 42 for c in answer.citations)


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_ask_409_thread_busy_retries(respx_mock, http):
    body = _sse_body([
        {"type": "text-delta", "id": "t1", "delta": "ok"},
        {"type": "finish"},
    ])
    busy = httpx.Response(
        409,
        json={"detail": {"errorCode": "THREAD_BUSY", "message": "busy"}},
        headers={"Retry-After": "1"},
    )
    success = httpx.Response(
        200, content=body, headers={"Content-Type": "text/event-stream"}
    )
    respx_mock.post("/api/v1/new_chat").mock(side_effect=[busy, success])
    client = NewChatClient(http, _BASE)
    answer = await client.ask(
        thread_id=1, search_space_id=2, user_query="hi", max_busy_retries=2
    )
    assert answer.text == "ok"


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_ask_409_exhausts_retries(respx_mock, http):
    busy = httpx.Response(
        409,
        json={"detail": {"errorCode": "TURN_CANCELLING", "message": "wait"}},
        headers={"Retry-After": "1"},
    )
    respx_mock.post("/api/v1/new_chat").mock(return_value=busy)
    client = NewChatClient(http, _BASE)
    with pytest.raises(ThreadBusyError):
        await client.ask(
            thread_id=1, search_space_id=2, user_query="hi", max_busy_retries=1
        )
