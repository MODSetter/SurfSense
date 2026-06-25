"""Behavior tests for the ``search_knowledge_base`` main-agent tool.

These exercise the tool through its public contract: seed a real document,
invoke the tool, and assert on the ``Command`` it returns — the rendered
``<retrieved_context>`` carries ``[n]`` labels and the citation registry handed
back on state is populated.
The tool's own DB session is redirected to the test session, and the embedding
leg is pinned so the search is deterministic without a live model.
"""

from __future__ import annotations

import contextlib
import uuid
from types import SimpleNamespace

import pytest
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from app.agents.chat.multi_agent_chat.main_agent.tools import search_knowledge_base
from app.agents.chat.multi_agent_chat.main_agent.tools.search_knowledge_base import (
    create_search_knowledge_base_tool,
)
from app.agents.chat.multi_agent_chat.shared.citations import CitationRegistry
from app.config import config
from app.db import Chunk, Document, DocumentType, Folder

pytestmark = pytest.mark.integration

_DIM = config.embedding_model_instance.dimension


def _axis(index: int) -> list[float]:
    vector = [0.0] * _DIM
    vector[index] = 1.0
    return vector


async def _add_document(
    db_session,
    *,
    search_space_id: int,
    title: str,
    text: str,
    folder_id: int | None = None,
):
    document = Document(
        title=title,
        document_type=DocumentType.FILE,
        content=text,
        content_hash=uuid.uuid4().hex,
        search_space_id=search_space_id,
        folder_id=folder_id,
        status={"state": "ready"},
    )
    db_session.add(document)
    await db_session.flush()
    db_session.add(
        Chunk(content=text, document_id=document.id, position=0, embedding=_axis(0))
    )
    await db_session.flush()
    return document


async def _add_folder(db_session, *, search_space_id: int, name: str = "Folder"):
    folder = Folder(name=name, position="0", search_space_id=search_space_id)
    db_session.add(folder)
    await db_session.flush()
    return folder


@pytest.fixture
def _tool_uses_test_session(db_session, monkeypatch):
    """Redirect the tool's ``shielded_async_session`` to the test transaction."""

    @contextlib.asynccontextmanager
    async def _session():
        yield db_session

    monkeypatch.setattr(search_knowledge_base, "shielded_async_session", _session)


@pytest.fixture
def _pinned_embedding(monkeypatch):
    monkeypatch.setattr(
        config.embedding_model_instance, "embed", lambda _query: _axis(0)
    )


async def _invoke(tool, query: str, state: dict | None = None, context=None):
    runtime = SimpleNamespace(
        state=state or {}, tool_call_id="call-1", context=context
    )
    return await tool.coroutine(query, runtime)


def _mentions(*, document_ids=(), folder_ids=()):
    return SimpleNamespace(
        mentioned_document_ids=list(document_ids),
        mentioned_folder_ids=list(folder_ids),
    )


async def test_tool_returns_retrieved_context_with_numbered_passages(
    db_session, db_search_space, _tool_uses_test_session, _pinned_embedding
):
    await _add_document(
        db_session,
        search_space_id=db_search_space.id,
        title="Asyncio Guide",
        text="The asyncio library enables concurrency.",
    )
    tool = create_search_knowledge_base_tool(search_space_id=db_search_space.id)

    result = await _invoke(tool, "asyncio")

    assert isinstance(result, Command)
    message = result.update["messages"][0]
    assert isinstance(message, ToolMessage)
    assert "<retrieved_context>" in message.content
    assert "[1]" in message.content


async def test_tool_populates_citation_registry_on_state(
    db_session, db_search_space, _tool_uses_test_session, _pinned_embedding
):
    await _add_document(
        db_session,
        search_space_id=db_search_space.id,
        title="Asyncio Guide",
        text="The asyncio library enables concurrency.",
    )
    tool = create_search_knowledge_base_tool(search_space_id=db_search_space.id)

    result = await _invoke(tool, "asyncio")

    registry = result.update["citation_registry"]
    assert isinstance(registry, CitationRegistry)
    assert registry.by_n  # at least one passage was registered as [n]


async def test_tool_reuses_existing_registry_numbering(
    db_session, db_search_space, _tool_uses_test_session, _pinned_embedding
):
    await _add_document(
        db_session,
        search_space_id=db_search_space.id,
        title="Asyncio Guide",
        text="The asyncio library enables concurrency.",
    )
    tool = create_search_knowledge_base_tool(search_space_id=db_search_space.id)

    first = await _invoke(tool, "asyncio")
    carried = first.update["citation_registry"]
    second = await _invoke(tool, "asyncio", state={"citation_registry": carried})

    # Same passage searched twice keeps a single [n] (find-or-create).
    assert len(second.update["citation_registry"].by_n) == 1


async def test_tool_reports_no_matches_without_touching_state(
    db_session, db_search_space, _tool_uses_test_session, _pinned_embedding
):
    tool = create_search_knowledge_base_tool(search_space_id=db_search_space.id)

    result = await _invoke(tool, "nonexistent-term-zzz")

    assert isinstance(result, str)
    assert "No knowledge-base matches" in result


async def test_tool_rejects_empty_query(
    db_search_space, _tool_uses_test_session, _pinned_embedding
):
    tool = create_search_knowledge_base_tool(search_space_id=db_search_space.id)

    result = await _invoke(tool, "   ")

    assert isinstance(result, str)
    assert "non-empty" in result


async def test_document_mention_confines_search_to_pinned_doc(
    db_session, db_search_space, _tool_uses_test_session, _pinned_embedding
):
    pinned = await _add_document(
        db_session,
        search_space_id=db_search_space.id,
        title="Pinned",
        text="asyncio appears in the pinned doc.",
    )
    await _add_document(
        db_session,
        search_space_id=db_search_space.id,
        title="Other",
        text="asyncio appears in the other doc.",
    )
    tool = create_search_knowledge_base_tool(search_space_id=db_search_space.id)

    result = await _invoke(
        tool, "asyncio", context=_mentions(document_ids=[pinned.id])
    )

    # Search is confined to the pinned doc: only its content is rendered.
    content = result.update["messages"][0].content
    assert "Pinned" in content
    assert "Other" not in content


async def test_folder_mention_confines_search_to_folder_documents(
    db_session, db_search_space, _tool_uses_test_session, _pinned_embedding
):
    folder = await _add_folder(db_session, search_space_id=db_search_space.id)
    await _add_document(
        db_session,
        search_space_id=db_search_space.id,
        title="Inside",
        text="asyncio appears inside the folder.",
        folder_id=folder.id,
    )
    await _add_document(
        db_session,
        search_space_id=db_search_space.id,
        title="Outside",
        text="asyncio appears outside the folder.",
    )
    tool = create_search_knowledge_base_tool(search_space_id=db_search_space.id)

    result = await _invoke(
        tool, "asyncio", context=_mentions(folder_ids=[folder.id])
    )

    # Search is confined to the folder's document: only its content is rendered.
    content = result.update["messages"][0].content
    assert "Inside" in content
    assert "Outside" not in content
