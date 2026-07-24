"""Behavior tests for the hybrid chunk retriever against a real Postgres.

These exercise ``search_chunks`` through its public surface only: seed real
documents/chunks, run a search, and assert on the returned ``DocumentHit``s —
never on SQL shape or internal ranking math. ``query_embedding`` is supplied
directly (a public parameter) so the semantic leg is deterministic instead of
depending on a live embedding model.
"""

from __future__ import annotations

import uuid

import pytest

from app.agents.chat.multi_agent_chat.shared.retrieval.hybrid_search import (
    search_chunks,
)
from app.agents.chat.multi_agent_chat.shared.retrieval.models import SearchScope
from app.config import config
from app.db import Chunk, Document, DocumentType, Workspace

pytestmark = pytest.mark.integration

_DIM = config.embedding_model_instance.dimension


def _axis(index: int) -> list[float]:
    """A unit vector pointing along one axis — orthogonal axes are dissimilar."""
    vector = [0.0] * _DIM
    vector[index] = 1.0
    return vector


async def _add_document(
    db_session,
    *,
    workspace_id: int,
    title: str = "Doc",
    document_type: DocumentType = DocumentType.FILE,
    state: str = "ready",
    chunks: list[tuple[str, int, list[float]]],
) -> Document:
    """Persist one document and its chunks; ``chunks`` is (content, position, embedding)."""
    document = Document(
        title=title,
        document_type=document_type,
        content="\n".join(content for content, _, _ in chunks),
        content_hash=uuid.uuid4().hex,
        workspace_id=workspace_id,
        status={"state": state},
    )
    db_session.add(document)
    await db_session.flush()
    for content, position, embedding in chunks:
        db_session.add(
            Chunk(
                content=content,
                document_id=document.id,
                position=position,
                embedding=embedding,
            )
        )
    await db_session.flush()
    return document


async def test_keyword_relevant_document_is_retrieved(db_session, db_workspace):
    document = await _add_document(
        db_session,
        workspace_id=db_workspace.id,
        title="Asyncio Guide",
        chunks=[("The asyncio library enables concurrency.", 0, _axis(0))],
    )

    results = await search_chunks(
        db_session,
        workspace_id=db_workspace.id,
        query="asyncio",
        scope=SearchScope(),
        top_k=5,
        query_embedding=_axis(99),
    )

    assert document.id in {hit.document_id for hit in results}


async def test_semantically_closest_document_ranks_first(db_session, db_workspace):
    aligned = await _add_document(
        db_session,
        workspace_id=db_workspace.id,
        title="Background Work",
        chunks=[("Parallel execution of background work.", 0, _axis(0))],
    )
    await _add_document(
        db_session,
        workspace_id=db_workspace.id,
        title="Dessert",
        chunks=[("Recipes for chocolate cake.", 0, _axis(1))],
    )

    results = await search_chunks(
        db_session,
        workspace_id=db_workspace.id,
        query="asynchronous coroutines",
        scope=SearchScope(),
        top_k=5,
        query_embedding=_axis(0),
    )

    assert results[0].document_id == aligned.id


async def test_results_stay_within_the_workspace(db_session, db_workspace):
    other_space = Workspace(name="Other Space", user_id=db_workspace.user_id)
    db_session.add(other_space)
    await db_session.flush()

    mine = await _add_document(
        db_session,
        workspace_id=db_workspace.id,
        chunks=[("Shared keyword asyncio here.", 0, _axis(0))],
    )
    foreign = await _add_document(
        db_session,
        workspace_id=other_space.id,
        chunks=[("Shared keyword asyncio here.", 0, _axis(0))],
    )

    results = await search_chunks(
        db_session,
        workspace_id=db_workspace.id,
        query="asyncio",
        scope=SearchScope(),
        top_k=5,
        query_embedding=_axis(0),
    )

    found = {hit.document_id for hit in results}
    assert mine.id in found and foreign.id not in found


async def test_document_ids_scope_pins_results(db_session, db_workspace):
    pinned = await _add_document(
        db_session,
        workspace_id=db_workspace.id,
        chunks=[("asyncio appears in the pinned doc.", 0, _axis(0))],
    )
    await _add_document(
        db_session,
        workspace_id=db_workspace.id,
        chunks=[("asyncio appears in the other doc too.", 0, _axis(0))],
    )

    results = await search_chunks(
        db_session,
        workspace_id=db_workspace.id,
        query="asyncio",
        scope=SearchScope(document_ids=(pinned.id,)),
        top_k=5,
        query_embedding=_axis(0),
    )

    assert {hit.document_id for hit in results} == {pinned.id}


async def test_deleting_documents_are_excluded(db_session, db_workspace):
    ready = await _add_document(
        db_session,
        workspace_id=db_workspace.id,
        chunks=[("asyncio in a ready document.", 0, _axis(0))],
    )
    deleting = await _add_document(
        db_session,
        workspace_id=db_workspace.id,
        state="deleting",
        chunks=[("asyncio in a deleting document.", 0, _axis(0))],
    )

    results = await search_chunks(
        db_session,
        workspace_id=db_workspace.id,
        query="asyncio",
        scope=SearchScope(),
        top_k=5,
        query_embedding=_axis(0),
    )

    found = {hit.document_id for hit in results}
    assert ready.id in found and deleting.id not in found


async def test_matched_chunks_are_ordered_for_reading(db_session, db_workspace):
    # Insert out of order, and give the later-position chunk the stronger
    # semantic score, so reading order differs from both insertion and score.
    document = await _add_document(
        db_session,
        workspace_id=db_workspace.id,
        chunks=[
            ("asyncio paragraph two.", 1, _axis(0)),
            ("asyncio paragraph one.", 0, _axis(50)),
        ],
    )

    results = await search_chunks(
        db_session,
        workspace_id=db_workspace.id,
        query="asyncio",
        scope=SearchScope(),
        top_k=5,
        query_embedding=_axis(0),
    )

    hit = next(hit for hit in results if hit.document_id == document.id)
    assert [chunk.position for chunk in hit.chunks] == [0, 1]


async def test_top_k_caps_the_number_of_documents(db_session, db_workspace):
    for index in range(3):
        await _add_document(
            db_session,
            workspace_id=db_workspace.id,
            title=f"Doc {index}",
            chunks=[(f"asyncio mentioned in doc {index}.", 0, _axis(index))],
        )

    results = await search_chunks(
        db_session,
        workspace_id=db_workspace.id,
        query="asyncio",
        scope=SearchScope(),
        top_k=2,
        query_embedding=_axis(0),
    )

    assert len(results) == 2
