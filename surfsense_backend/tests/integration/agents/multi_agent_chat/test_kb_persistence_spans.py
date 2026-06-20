"""NOTE writes must carry the same char spans as the indexing pipeline.

``_create_document`` / ``_update_document`` are the cloud agent's KB write
paths. They must chunk through the shared span chunker so every persisted
chunk resolves back to an exact slice of ``source_markdown`` for citations.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.agents.chat.multi_agent_chat.main_agent.middleware.kb_persistence import (
    middleware as kb,
)
from app.db import Chunk

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_BODY = "Intro paragraph.\n\nBody paragraph with detail.\n\nOutro paragraph."
_NEW_BODY = "Rewritten intro.\n\nFresh body content.\n\nNew closing line."


async def _ordered_chunks(session, doc_id: int) -> list[Chunk]:
    rows = await session.execute(
        select(Chunk).where(Chunk.document_id == doc_id).order_by(Chunk.position)
    )
    return list(rows.scalars().all())


def _assert_spans_resolve(source_markdown: str, chunks: list[Chunk]) -> None:
    assert chunks
    for chunk in chunks:
        assert chunk.start_char is not None
        assert chunk.end_char is not None
        assert source_markdown[chunk.start_char : chunk.end_char] == chunk.content


@pytest.mark.usefixtures("patched_embed_texts")
async def test_note_create_populates_chunk_spans(
    db_session, db_search_space, db_user
) -> None:
    doc = await kb._create_document(
        db_session,
        virtual_path="/documents/note.md",
        content=_BODY,
        search_space_id=db_search_space.id,
        created_by_id=str(db_user.id),
    )
    await db_session.flush()

    chunks = await _ordered_chunks(db_session, doc.id)
    _assert_spans_resolve(doc.source_markdown, chunks)


@pytest.mark.usefixtures("patched_embed_texts")
async def test_note_update_refreshes_chunk_spans(
    db_session, db_search_space, db_user
) -> None:
    doc = await kb._create_document(
        db_session,
        virtual_path="/documents/note.md",
        content=_BODY,
        search_space_id=db_search_space.id,
        created_by_id=str(db_user.id),
    )
    await db_session.flush()

    updated = await kb._update_document(
        db_session,
        doc_id=doc.id,
        content=_NEW_BODY,
        virtual_path="/documents/note.md",
        search_space_id=db_search_space.id,
    )
    await db_session.flush()

    assert updated is not None
    chunks = await _ordered_chunks(db_session, updated.id)
    _assert_spans_resolve(updated.source_markdown, chunks)
