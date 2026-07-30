"""Entry point: serve chunk embeddings from cache, embedding only on a miss.

Embeddings are a pure function of the markdown, the embedding model, and the
chunker -- so identical markdown is chunked and embedded once and reused across
workspaces, even when it came from different sources.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass

import numpy as np

from app.config import config
from app.indexing_pipeline.cache.eligibility import is_embedding_cacheable
from app.indexing_pipeline.cache.schemas import CachedChunk, EmbeddingKey, EmbeddingSet
from app.indexing_pipeline.cache.service import EmbeddingCacheService
from app.indexing_pipeline.cache.settings import load_embedding_cache_settings
from app.indexing_pipeline.document_chunker import (
    LineChunk,
    attach_line_spans,
    chunk_text,
    chunk_text_hybrid,
)
from app.indexing_pipeline.document_embedder import embed_texts
from app.observability import metrics

logger = logging.getLogger(__name__)

ChunkPair = tuple[str, np.ndarray]


@dataclass(frozen=True, slots=True)
class EmbeddedChunk:
    """One chunk ready to persist: its text, its line range, and its vector."""

    text: str
    start_line: int
    end_line: int
    embedding: np.ndarray


async def build_chunk_embeddings(
    markdown: str, *, use_code_chunker: bool
) -> tuple[np.ndarray, list[EmbeddedChunk]]:
    """Return the document-level vector and the ordered chunks to persist.

    Drop-in for the inline chunk+embed step; reuses prior output when the same
    markdown has already been embedded with the current model and chunker.

    Line spans are attached here rather than cached: they are a pure function of
    the markdown and the chunk texts, both of which every caller already holds,
    so caching them would buy nothing and would invalidate every existing entry.
    """
    settings = load_embedding_cache_settings()
    chunker_kind = "code" if use_code_chunker else "hybrid"
    embedding_dim = getattr(config.embedding_model_instance, "dimension", None)

    cacheable = is_embedding_cacheable(
        cache_enabled=settings.enabled,
        embedding_model=config.EMBEDDING_MODEL,
        embedding_dim=embedding_dim,
    )
    if not cacheable:
        summary_embedding, chunk_pairs = await _compute(
            markdown, use_code_chunker=use_code_chunker
        )
        return summary_embedding, _with_line_spans(markdown, chunk_pairs)

    key = EmbeddingKey(
        markdown_sha256=_hash_text(markdown),
        embedding_model=config.EMBEDDING_MODEL,
        embedding_dim=int(embedding_dim),
        chunker_kind=chunker_kind,
        chunker_version=settings.chunker_version,
    )

    cached = await _recall(key)
    if cached is not None:
        metrics.record_embedding_cache_lookup(
            embedding_model=key.embedding_model,
            chunker_kind=chunker_kind,
            outcome="hit",
        )
        logger.debug("Embedding cache hit for %s", key.markdown_sha256)
        return cached.summary_embedding, _with_line_spans(
            markdown, [(c.text, c.embedding) for c in cached.chunks]
        )

    metrics.record_embedding_cache_lookup(
        embedding_model=key.embedding_model, chunker_kind=chunker_kind, outcome="miss"
    )
    summary_embedding, chunk_pairs = await _compute(
        markdown, use_code_chunker=use_code_chunker
    )
    await _remember(key, summary_embedding, chunk_pairs)
    return summary_embedding, _with_line_spans(markdown, chunk_pairs)


async def chunk_markdown(markdown: str, *, use_code_chunker: bool) -> list[str]:
    """Chunk markdown into ordered texts with the pipeline's chunker selection."""
    if use_code_chunker:
        return await asyncio.to_thread(chunk_text, markdown, use_code_chunker=True)
    # Table-aware hybrid chunker keeps Markdown tables intact (issue #1334).
    return await asyncio.to_thread(chunk_text_hybrid, markdown)


async def chunk_markdown_with_lines(
    markdown: str, *, use_code_chunker: bool
) -> list[LineChunk]:
    """Chunk markdown into ordered texts, each carrying its line range."""
    texts = await chunk_markdown(markdown, use_code_chunker=use_code_chunker)
    return attach_line_spans(markdown, texts)


async def embed_batch(texts: list[str]) -> list[np.ndarray]:
    """Embed texts in one batch off the event loop."""
    return await asyncio.to_thread(embed_texts, texts)


async def _compute(
    markdown: str, *, use_code_chunker: bool
) -> tuple[np.ndarray, list[ChunkPair]]:
    chunk_texts = await chunk_markdown(markdown, use_code_chunker=use_code_chunker)
    embeddings = await embed_batch([markdown, *chunk_texts])
    summary_embedding, *chunk_embeddings = embeddings
    return summary_embedding, list(zip(chunk_texts, chunk_embeddings, strict=False))


async def _recall(key: EmbeddingKey) -> EmbeddingSet | None:
    # Caching is best-effort: any failure falls through to a normal embed.
    try:
        from app.tasks.celery_tasks import get_celery_session_maker

        async with get_celery_session_maker()() as session:
            return await EmbeddingCacheService(session).recall(key)
    except Exception:
        logger.warning("Embedding cache recall failed; embedding fresh", exc_info=True)
        return None


async def _remember(
    key: EmbeddingKey, summary_embedding: np.ndarray, chunk_pairs: list[ChunkPair]
) -> None:
    try:
        from app.tasks.celery_tasks import get_celery_session_maker

        embedding_set = EmbeddingSet(
            summary_embedding=summary_embedding,
            chunks=[CachedChunk(text=text, embedding=vec) for text, vec in chunk_pairs],
        )
        async with get_celery_session_maker()() as session:
            await EmbeddingCacheService(session).remember(key, embedding_set)
    except Exception:
        logger.warning("Embedding cache write failed; result not cached", exc_info=True)


def _with_line_spans(markdown: str, pairs: list[ChunkPair]) -> list[EmbeddedChunk]:
    spans = attach_line_spans(markdown, [text for text, _ in pairs])
    return [
        EmbeddedChunk(
            text=span.text,
            start_line=span.start_line,
            end_line=span.end_line,
            embedding=embedding,
        )
        for (_, embedding), span in zip(pairs, spans, strict=True)
    ]


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
