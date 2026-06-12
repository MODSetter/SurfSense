"""Entry point: serve chunk embeddings from cache, embedding only on a miss.

Embeddings are a pure function of the markdown, the embedding model, and the
chunker -- so identical markdown is chunked and embedded once and reused across
workspaces, even when it came from different sources.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging

import numpy as np

from app.config import config
from app.indexing_pipeline.cache.eligibility import is_index_cacheable
from app.indexing_pipeline.cache.schemas import CachedChunk, EmbeddingKey, EmbeddingSet
from app.indexing_pipeline.cache.service import IndexCacheService
from app.indexing_pipeline.cache.settings import load_index_cache_settings
from app.indexing_pipeline.document_chunker import chunk_text, chunk_text_hybrid
from app.indexing_pipeline.document_embedder import embed_texts
from app.observability import metrics

logger = logging.getLogger(__name__)

ChunkPair = tuple[str, np.ndarray]


async def build_chunk_embeddings(
    markdown: str, *, use_code_chunker: bool
) -> tuple[np.ndarray, list[ChunkPair]]:
    """Return the document-level vector and ordered ``(chunk_text, vector)`` pairs.

    Drop-in for the inline chunk+embed step; reuses prior output when the same
    markdown has already been embedded with the current model and chunker.
    """
    settings = load_index_cache_settings()
    chunker_kind = "code" if use_code_chunker else "hybrid"
    embedding_dim = getattr(config.embedding_model_instance, "dimension", None)

    cacheable = is_index_cacheable(
        cache_enabled=settings.enabled,
        embedding_model=config.EMBEDDING_MODEL,
        embedding_dim=embedding_dim,
    )
    if not cacheable:
        return await _compute(markdown, use_code_chunker=use_code_chunker)

    key = EmbeddingKey(
        markdown_sha256=_hash_text(markdown),
        embedding_model=config.EMBEDDING_MODEL,
        embedding_dim=int(embedding_dim),
        chunker_kind=chunker_kind,
        chunker_version=settings.chunker_version,
    )

    cached = await _recall(key)
    if cached is not None:
        metrics.record_index_cache_lookup(
            embedding_model=key.embedding_model, chunker_kind=chunker_kind, outcome="hit"
        )
        logger.debug("Index cache hit for %s", key.markdown_sha256)
        return cached.summary_embedding, [(c.text, c.embedding) for c in cached.chunks]

    metrics.record_index_cache_lookup(
        embedding_model=key.embedding_model, chunker_kind=chunker_kind, outcome="miss"
    )
    summary_embedding, chunk_pairs = await _compute(
        markdown, use_code_chunker=use_code_chunker
    )
    await _remember(key, summary_embedding, chunk_pairs)
    return summary_embedding, chunk_pairs


async def _compute(
    markdown: str, *, use_code_chunker: bool
) -> tuple[np.ndarray, list[ChunkPair]]:
    if use_code_chunker:
        chunk_texts = await asyncio.to_thread(
            chunk_text, markdown, use_code_chunker=True
        )
    else:
        # Table-aware hybrid chunker keeps Markdown tables intact (issue #1334).
        chunk_texts = await asyncio.to_thread(chunk_text_hybrid, markdown)

    embeddings = await asyncio.to_thread(embed_texts, [markdown, *chunk_texts])
    summary_embedding, *chunk_embeddings = embeddings
    return summary_embedding, list(zip(chunk_texts, chunk_embeddings, strict=False))


async def _recall(key: EmbeddingKey) -> EmbeddingSet | None:
    # Caching is best-effort: any failure falls through to a normal embed.
    try:
        from app.tasks.celery_tasks import get_celery_session_maker

        async with get_celery_session_maker()() as session:
            return await IndexCacheService(session).recall(key)
    except Exception:
        logger.warning("Index cache recall failed; embedding fresh", exc_info=True)
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
            await IndexCacheService(session).remember(key, embedding_set)
    except Exception:
        logger.warning("Index cache write failed; result not cached", exc_info=True)


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
