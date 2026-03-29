"""Shared fixtures for retriever integration tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config as app_config
from app.db import Chunk, Document, DocumentType, SearchSpace, User

EMBEDDING_DIM = app_config.embedding_model_instance.dimension
DUMMY_EMBEDDING = [0.1] * EMBEDDING_DIM


def _make_document(
    *,
    title: str,
    document_type: DocumentType,
    content: str,
    search_space_id: int,
    created_by_id: str,
) -> Document:
    uid = uuid.uuid4().hex[:12]
    return Document(
        title=title,
        document_type=document_type,
        content=content,
        content_hash=f"content-{uid}",
        unique_identifier_hash=f"uid-{uid}",
        source_markdown=content,
        search_space_id=search_space_id,
        created_by_id=created_by_id,
        embedding=DUMMY_EMBEDDING,
        updated_at=datetime.now(UTC),
        status={"state": "ready"},
    )


def _make_chunk(*, content: str, document_id: int) -> Chunk:
    return Chunk(
        content=content,
        document_id=document_id,
        embedding=DUMMY_EMBEDDING,
    )


@pytest_asyncio.fixture
async def seed_large_doc(
    db_session: AsyncSession, db_user: User, db_search_space: SearchSpace
):
    """Insert a document with 35 chunks (more than _MAX_FETCH_CHUNKS_PER_DOC=20).

    Also inserts a small 3-chunk document for diversity testing.
    Returns a dict with ``large_doc``, ``small_doc``, ``search_space``, ``user``,
    and ``large_chunk_ids`` (all 35 chunk IDs).
    """
    user_id = str(db_user.id)
    space_id = db_search_space.id

    large_doc = _make_document(
        title="Large PDF Document",
        document_type=DocumentType.FILE,
        content="large document about quarterly performance reviews and budgets",
        search_space_id=space_id,
        created_by_id=user_id,
    )
    small_doc = _make_document(
        title="Small Note",
        document_type=DocumentType.NOTE,
        content="quarterly performance review summary note",
        search_space_id=space_id,
        created_by_id=user_id,
    )

    db_session.add_all([large_doc, small_doc])
    await db_session.flush()

    large_chunks = []
    for i in range(35):
        chunk = _make_chunk(
            content=f"chunk {i} about quarterly performance review section {i}",
            document_id=large_doc.id,
        )
        large_chunks.append(chunk)

    small_chunks = [
        _make_chunk(
            content="quarterly performance review summary note content",
            document_id=small_doc.id,
        ),
    ]

    db_session.add_all(large_chunks + small_chunks)
    await db_session.flush()

    return {
        "large_doc": large_doc,
        "small_doc": small_doc,
        "large_chunk_ids": [c.id for c in large_chunks],
        "small_chunk_ids": [c.id for c in small_chunks],
        "search_space": db_search_space,
        "user": db_user,
    }
