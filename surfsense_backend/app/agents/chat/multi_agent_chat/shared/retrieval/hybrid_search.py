"""Hybrid (semantic + keyword) chunk search with reciprocal-rank fusion.

Only matched chunks are citable, so the fused result already holds every passage
shown — there is no second per-document fetch. Returns the top ``top_k``
documents, each carrying its matched chunks in reading order.
"""

from __future__ import annotations

import asyncio
import contextlib

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.config import config
from app.db import Chunk, Document, DocumentType

from .models import ChunkHit, DocumentHit, SearchScope

_RRF_K = 60
_CANDIDATE_MULTIPLIER = 5  # fused-chunk pool size relative to top_k
_MAX_PASSAGES_PER_DOC = 12


async def search_chunks(
    db_session: AsyncSession,
    *,
    search_space_id: int,
    query: str,
    scope: SearchScope,
    top_k: int,
    query_embedding: list[float] | None = None,
) -> list[DocumentHit]:
    """Top ``top_k`` documents for ``query`` within scope, each with its chunks."""
    document_types = _resolve_document_types(scope.document_types)
    if document_types == []:  # types requested, none recognized → nothing matches
        return []

    if query_embedding is None:
        query_embedding = await asyncio.to_thread(
            config.embedding_model_instance.embed, query
        )

    conditions = _base_conditions(search_space_id, scope, document_types)
    rows = await _fused_chunks(
        db_session,
        query=query,
        query_embedding=query_embedding,
        conditions=conditions,
        candidate_pool=top_k * _CANDIDATE_MULTIPLIER,
    )
    return _group_into_documents(rows, top_k=top_k)


def _resolve_document_types(
    raw: tuple[str, ...] | None,
) -> list[DocumentType] | None:
    """Map type names to enum members; ``None`` when unfiltered, ``[]`` if all unknown."""
    if not raw:
        return None
    resolved: list[DocumentType] = []
    for name in raw:
        with contextlib.suppress(KeyError):
            resolved.append(DocumentType[name])
    return resolved


def _base_conditions(
    search_space_id: int,
    scope: SearchScope,
    document_types: list[DocumentType] | None,
) -> list:
    """Filters shared by both search legs."""
    conditions = [
        Document.search_space_id == search_space_id,
        func.coalesce(Document.status["state"].astext, "ready") != "deleting",
    ]
    if document_types:
        conditions.append(Document.document_type.in_(document_types))
    if scope.document_ids:
        conditions.append(Document.id.in_(scope.document_ids))
    if scope.start_date is not None:
        conditions.append(Document.updated_at >= scope.start_date)
    if scope.end_date is not None:
        conditions.append(Document.updated_at <= scope.end_date)
    return conditions


async def _fused_chunks(
    db_session: AsyncSession,
    *,
    query: str,
    query_embedding: list[float],
    conditions: list,
    candidate_pool: int,
):
    """Run semantic + keyword legs and fuse them with RRF; return (Chunk, score) rows."""
    tsvector = func.to_tsvector("english", Chunk.content)
    tsquery = func.plainto_tsquery("english", query)

    semantic = (
        select(
            Chunk.id,
            func.rank()
            .over(order_by=Chunk.embedding.op("<=>")(query_embedding))
            .label("rank"),
        )
        .join(Document, Chunk.document_id == Document.id)
        .where(*conditions)
        .order_by(Chunk.embedding.op("<=>")(query_embedding))
        .limit(candidate_pool)
        .cte("semantic_search")
    )

    keyword = (
        select(
            Chunk.id,
            func.rank()
            .over(order_by=func.ts_rank_cd(tsvector, tsquery).desc())
            .label("rank"),
        )
        .join(Document, Chunk.document_id == Document.id)
        .where(*conditions)
        .where(tsvector.op("@@")(tsquery))
        .order_by(func.ts_rank_cd(tsvector, tsquery).desc())
        .limit(candidate_pool)
        .cte("keyword_search")
    )

    fused = (
        select(
            Chunk,
            (
                func.coalesce(1.0 / (_RRF_K + semantic.c.rank), 0.0)
                + func.coalesce(1.0 / (_RRF_K + keyword.c.rank), 0.0)
            ).label("score"),
        )
        .select_from(
            semantic.outerjoin(keyword, semantic.c.id == keyword.c.id, full=True)
        )
        .join(Chunk, Chunk.id == func.coalesce(semantic.c.id, keyword.c.id))
        .options(joinedload(Chunk.document))
        .order_by(text("score DESC"))
        .limit(candidate_pool)
    )

    result = await db_session.execute(fused)
    return result.all()


def _group_into_documents(rows, *, top_k: int) -> list[DocumentHit]:
    """Group fused chunks by document, keep the top_k best, order chunks for reading."""
    chunks_by_doc: dict[int, list[ChunkHit]] = {}
    document_by_id: dict[int, Document] = {}
    best_score: dict[int, float] = {}
    order: list[int] = []

    for chunk, score in rows:
        document_id = chunk.document.id
        if document_id not in chunks_by_doc:
            chunks_by_doc[document_id] = []
            document_by_id[document_id] = chunk.document
            best_score[document_id] = float(score)
            order.append(document_id)
        chunks_by_doc[document_id].append(
            ChunkHit(
                chunk_id=chunk.id,
                content=chunk.content,
                position=chunk.position,
                score=float(score),
            )
        )

    return [
        DocumentHit(
            document_id=document_id,
            title=document_by_id[document_id].title,
            document_type=_type_value(document_by_id[document_id]),
            metadata=document_by_id[document_id].document_metadata or {},
            score=best_score[document_id],
            chunks=_reading_order(chunks_by_doc[document_id]),
        )
        for document_id in order[:top_k]
    ]


def _reading_order(chunks: list[ChunkHit]) -> list[ChunkHit]:
    """Keep the most relevant chunks, then present them in document order."""
    most_relevant = sorted(chunks, key=lambda c: c.score, reverse=True)[
        :_MAX_PASSAGES_PER_DOC
    ]
    return sorted(most_relevant, key=lambda c: c.position)


def _type_value(document: Document) -> str | None:
    document_type = getattr(document, "document_type", None)
    return document_type.value if document_type is not None else None


__all__ = ["search_chunks"]
