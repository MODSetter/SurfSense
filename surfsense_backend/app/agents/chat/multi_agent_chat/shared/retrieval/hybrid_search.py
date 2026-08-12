"""Hybrid (semantic + keyword) chunk search with reciprocal-rank fusion.

Only matched chunks are citable, so fused results already hold every passage
shown — there is no second per-source fetch. ``search_knowledge_base`` globally
fuses documents and artifacts; ``search_chunks`` preserves the legacy
document-only contract used by REST and report callers.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.artifacts.persistence import Artifact, ArtifactChunk
from app.config import config
from app.db import Chunk, Document, DocumentType
from app.observability import metrics, otel
from app.utils.perf import get_perf_logger

from .models import ArtifactHit, ChunkHit, DocumentHit, KnowledgeHit, SearchScope

_RRF_K = 60
_CANDIDATE_MULTIPLIER = 5  # fused-chunk pool size relative to top_k
_MAX_PASSAGES_PER_DOC = 12
_SURFACE = "chunks"


@dataclass(frozen=True)
class _Candidate:
    domain: Literal["document", "artifact"]
    chunk_id: int
    parent_id: int
    title: str
    subtype: str | None
    path: str | None
    metadata: dict
    content: str
    position: int
    metric: float

    @property
    def key(self) -> tuple[str, int]:
        return (self.domain, self.chunk_id)


async def search_chunks(
    db_session: AsyncSession,
    *,
    workspace_id: int,
    query: str,
    scope: SearchScope,
    top_k: int,
    query_embedding: list[float] | None = None,
) -> list[DocumentHit]:
    """Top ``top_k`` documents for ``query`` within scope, each with its chunks.

    Instrumented seam: traces the search, records its duration, and logs a
    timing line. The fusion logic lives in :func:`_search`.
    """
    started = time.perf_counter()
    with otel.kb_search_span(
        workspace_id=workspace_id,
        query_chars=len(query),
        extra={"search.surface": _SURFACE, "search.mode": "hybrid"},
    ) as span:
        try:
            documents = await _search(
                db_session,
                workspace_id=workspace_id,
                query=query,
                scope=scope,
                top_k=top_k,
                query_embedding=query_embedding,
            )
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000
            metrics.record_kb_search_duration(
                elapsed_ms, workspace_id=workspace_id, surface=_SURFACE
            )
        span.set_attribute("result.count", len(documents))
        get_perf_logger().info(
            "[chunk_search] hybrid in %.3fs docs=%d space=%d",
            elapsed_ms / 1000,
            len(documents),
            workspace_id,
        )
        return documents


async def search_knowledge_base(
    db_session: AsyncSession,
    *,
    workspace_id: int,
    query: str,
    scope: SearchScope,
    top_k: int,
    query_embedding: list[float] | None = None,
) -> list[KnowledgeHit]:
    """Search document and artifact chunks with one embedding and one global RRF.

    Document and artifact primary keys occupy independent sequences, so every
    candidate and group is keyed by ``(domain, id)`` throughout fusion.
    """
    if query_embedding is None:
        query_embedding = await asyncio.to_thread(
            config.embedding_model_instance.embed, query
        )

    document_types = _resolve_document_types(scope.document_types)
    candidate_pool = top_k * _CANDIDATE_MULTIPLIER
    document_conditions = (
        []
        if document_types == []
        else _base_conditions(workspace_id, scope, document_types)
    )
    artifact_conditions = _artifact_conditions(workspace_id, scope)

    semantic: list[_Candidate] = []
    keyword: list[_Candidate] = []
    if document_conditions:
        semantic.extend(
            await _document_candidates(
                db_session,
                query=query,
                query_embedding=query_embedding,
                conditions=document_conditions,
                limit=candidate_pool,
                semantic=True,
            )
        )
        keyword.extend(
            await _document_candidates(
                db_session,
                query=query,
                query_embedding=query_embedding,
                conditions=document_conditions,
                limit=candidate_pool,
                semantic=False,
            )
        )
    if artifact_conditions is not None:
        semantic.extend(
            await _artifact_candidates(
                db_session,
                query=query,
                query_embedding=query_embedding,
                conditions=artifact_conditions,
                limit=candidate_pool,
                semantic=True,
            )
        )
        keyword.extend(
            await _artifact_candidates(
                db_session,
                query=query,
                query_embedding=query_embedding,
                conditions=artifact_conditions,
                limit=candidate_pool,
                semantic=False,
            )
        )

    semantic.sort(key=lambda candidate: candidate.metric)
    keyword.sort(key=lambda candidate: candidate.metric, reverse=True)
    return _fuse_and_group(semantic, keyword, top_k=top_k, pool=candidate_pool)


async def _search(
    db_session: AsyncSession,
    *,
    workspace_id: int,
    query: str,
    scope: SearchScope,
    top_k: int,
    query_embedding: list[float] | None,
) -> list[DocumentHit]:
    """Fusion search itself: resolve scope, fuse the two legs, group by document."""
    document_types = _resolve_document_types(scope.document_types)
    if document_types == []:  # types requested, none recognized → nothing matches
        return []

    if query_embedding is None:
        query_embedding = await asyncio.to_thread(
            config.embedding_model_instance.embed, query
        )

    conditions = _base_conditions(workspace_id, scope, document_types)
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
    workspace_id: int,
    scope: SearchScope,
    document_types: list[DocumentType] | None,
) -> list:
    """Filters shared by both search legs."""
    conditions = [
        Document.workspace_id == workspace_id,
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


def _artifact_conditions(workspace_id: int, scope: SearchScope) -> list | None:
    """Artifact scope, or ``None`` when explicit document pins exclude artifacts."""
    if scope.document_ids:
        return None
    conditions = [
        Artifact.workspace_id == workspace_id,
        Artifact.indexing_status == "ready",
        Artifact.indexed_version == Artifact.version,
    ]
    if scope.start_date is not None:
        conditions.append(Artifact.updated_at >= scope.start_date)
    if scope.end_date is not None:
        conditions.append(Artifact.updated_at <= scope.end_date)
    return conditions


async def _document_candidates(
    session: AsyncSession,
    *,
    query: str,
    query_embedding: list[float],
    conditions: list,
    limit: int,
    semantic: bool,
) -> list[_Candidate]:
    tsvector = func.to_tsvector("english", Chunk.content)
    metric = (
        Chunk.embedding.op("<=>")(query_embedding)
        if semantic
        else func.ts_rank_cd(tsvector, func.plainto_tsquery("english", query))
    )
    statement = (
        select(
            Chunk.id,
            Document.id,
            Document.title,
            Document.document_type,
            Document.document_metadata,
            Chunk.content,
            Chunk.position,
            metric.label("metric"),
        )
        .join(Document, Chunk.document_id == Document.id)
        .where(*conditions)
    )
    if semantic:
        statement = statement.where(Chunk.embedding.is_not(None)).order_by(metric)
    else:
        statement = statement.where(
            tsvector.op("@@")(func.plainto_tsquery("english", query))
        ).order_by(metric.desc())
    rows = (await session.execute(statement.limit(limit))).all()
    return [
        _Candidate(
            domain="document",
            chunk_id=chunk_id,
            parent_id=document_id,
            title=title,
            subtype=document_type.value if document_type is not None else None,
            path=None,
            metadata=metadata or {},
            content=content,
            position=position,
            metric=float(metric_value),
        )
        for (
            chunk_id,
            document_id,
            title,
            document_type,
            metadata,
            content,
            position,
            metric_value,
        ) in rows
    ]


async def _artifact_candidates(
    session: AsyncSession,
    *,
    query: str,
    query_embedding: list[float],
    conditions: list,
    limit: int,
    semantic: bool,
) -> list[_Candidate]:
    tsvector = func.to_tsvector("english", ArtifactChunk.content)
    metric = (
        ArtifactChunk.embedding.op("<=>")(query_embedding)
        if semantic
        else func.ts_rank_cd(tsvector, func.plainto_tsquery("english", query))
    )
    statement = (
        select(
            ArtifactChunk.id,
            Artifact.id,
            Artifact.title,
            Artifact.format,
            Artifact.path,
            Artifact.artifact_metadata,
            ArtifactChunk.content,
            ArtifactChunk.position,
            metric.label("metric"),
        )
        .join(Artifact, ArtifactChunk.artifact_id == Artifact.id)
        .where(*conditions)
    )
    if semantic:
        statement = statement.where(ArtifactChunk.embedding.is_not(None)).order_by(
            metric
        )
    else:
        statement = statement.where(
            tsvector.op("@@")(func.plainto_tsquery("english", query))
        ).order_by(metric.desc())
    rows = (await session.execute(statement.limit(limit))).all()
    return [
        _Candidate(
            domain="artifact",
            chunk_id=chunk_id,
            parent_id=artifact_id,
            title=title,
            subtype=artifact_format,
            path=path,
            metadata=metadata or {},
            content=content,
            position=position,
            metric=float(metric_value),
        )
        for (
            chunk_id,
            artifact_id,
            title,
            artifact_format,
            path,
            metadata,
            content,
            position,
            metric_value,
        ) in rows
    ]


def _fuse_and_group(
    semantic: list[_Candidate],
    keyword: list[_Candidate],
    *,
    top_k: int,
    pool: int,
) -> list[KnowledgeHit]:
    candidates = {candidate.key: candidate for candidate in [*semantic, *keyword]}
    scores: dict[tuple[str, int], float] = {}
    for ranked in (semantic, keyword):
        for rank, candidate in enumerate(ranked, start=1):
            scores[candidate.key] = scores.get(candidate.key, 0.0) + 1.0 / (
                _RRF_K + rank
            )

    ranked_keys = sorted(scores, key=scores.__getitem__, reverse=True)[:pool]
    chunks_by_parent: dict[tuple[str, int], list[ChunkHit]] = {}
    representative: dict[tuple[str, int], _Candidate] = {}
    best_score: dict[tuple[str, int], float] = {}
    parent_order: list[tuple[str, int]] = []
    for key in ranked_keys:
        candidate = candidates[key]
        parent_key = (candidate.domain, candidate.parent_id)
        if parent_key not in chunks_by_parent:
            chunks_by_parent[parent_key] = []
            representative[parent_key] = candidate
            best_score[parent_key] = scores[key]
            parent_order.append(parent_key)
        chunks_by_parent[parent_key].append(
            ChunkHit(
                chunk_id=candidate.chunk_id,
                content=candidate.content,
                position=candidate.position,
                score=scores[key],
            )
        )

    hits: list[KnowledgeHit] = []
    for parent_key in parent_order[:top_k]:
        candidate = representative[parent_key]
        chunks = _reading_order(chunks_by_parent[parent_key])
        if candidate.domain == "artifact":
            hits.append(
                ArtifactHit(
                    artifact_id=candidate.parent_id,
                    title=candidate.title,
                    format=candidate.subtype or "artifact",
                    path=candidate.path or f"/artifacts/{candidate.parent_id}",
                    metadata=candidate.metadata,
                    score=best_score[parent_key],
                    chunks=chunks,
                )
            )
        else:
            hits.append(
                DocumentHit(
                    document_id=candidate.parent_id,
                    title=candidate.title,
                    document_type=candidate.subtype,
                    metadata=candidate.metadata,
                    score=best_score[parent_key],
                    chunks=chunks,
                )
            )
    return hits


__all__ = ["search_chunks", "search_knowledge_base"]
