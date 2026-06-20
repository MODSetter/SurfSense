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
from app.indexing_pipeline.cache.eligibility import is_embedding_cacheable
from app.indexing_pipeline.cache.schemas import CachedChunk, EmbeddingKey, EmbeddingSet
from app.indexing_pipeline.cache.service import EmbeddingCacheService
from app.indexing_pipeline.cache.settings import load_embedding_cache_settings
from app.indexing_pipeline.document_chunker import ChunkSlice, chunk_markdown_with_spans
from app.indexing_pipeline.document_embedder import embed_texts
from app.observability import metrics

logger = logging.getLogger(__name__)

SliceEmbedding = tuple[ChunkSlice, np.ndarray]


async def build_chunk_embeddings(
    markdown: str, *, use_code_chunker: bool
) -> tuple[np.ndarray, list[SliceEmbedding]]:
    """Return the document-level vector and ordered ``(ChunkSlice, vector)`` pairs.

    Slices are always recomputed (cheap) so their char spans are exact; only the
    embeddings are cached, reused when the same markdown was embedded with the
    current model and chunker.
    """
    slices = await chunk_slices(markdown, use_code_chunker=use_code_chunker)

    settings = load_embedding_cache_settings()
    chunker_kind = "code" if use_code_chunker else "hybrid"
    embedding_dim = getattr(config.embedding_model_instance, "dimension", None)

    cacheable = is_embedding_cacheable(
        cache_enabled=settings.enabled,
        embedding_model=config.EMBEDDING_MODEL,
        embedding_dim=embedding_dim,
    )
    if not cacheable:
        return await _compute(markdown, slices)

    key = EmbeddingKey(
        markdown_sha256=_hash_text(markdown),
        embedding_model=config.EMBEDDING_MODEL,
        embedding_dim=int(embedding_dim),
        chunker_kind=chunker_kind,
        chunker_version=settings.chunker_version,
    )

    cached = await _recall(key)
    if cached is not None and _aligns(cached, slices):
        metrics.record_embedding_cache_lookup(
            embedding_model=key.embedding_model,
            chunker_kind=chunker_kind,
            outcome="hit",
        )
        logger.debug("Embedding cache hit for %s", key.markdown_sha256)
        return cached.summary_embedding, list(
            zip(slices, (c.embedding for c in cached.chunks), strict=True)
        )

    metrics.record_embedding_cache_lookup(
        embedding_model=key.embedding_model, chunker_kind=chunker_kind, outcome="miss"
    )
    summary_embedding, pairs = await _compute(markdown, slices)
    await _remember(key, summary_embedding, pairs)
    return summary_embedding, pairs


async def chunk_slices(markdown: str, *, use_code_chunker: bool) -> list[ChunkSlice]:
    """Chunk markdown into ordered, char-addressed slices off the event loop."""
    return await asyncio.to_thread(
        chunk_markdown_with_spans, markdown, use_code_chunker
    )


async def embed_batch(texts: list[str]) -> list[np.ndarray]:
    """Embed texts in one batch off the event loop."""
    return await asyncio.to_thread(embed_texts, texts)


def _aligns(cached: EmbeddingSet, slices: list[ChunkSlice]) -> bool:
    """A hit is only usable if its texts still match the current chunking."""
    return len(cached.chunks) == len(slices) and all(
        c.text == s.text for c, s in zip(cached.chunks, slices, strict=True)
    )


async def _compute(
    markdown: str, slices: list[ChunkSlice]
) -> tuple[np.ndarray, list[SliceEmbedding]]:
    embeddings = await embed_batch([markdown, *(s.text for s in slices)])
    summary_embedding, *chunk_embeddings = embeddings
    return summary_embedding, list(zip(slices, chunk_embeddings, strict=True))


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
    key: EmbeddingKey, summary_embedding: np.ndarray, pairs: list[SliceEmbedding]
) -> None:
    try:
        from app.tasks.celery_tasks import get_celery_session_maker

        embedding_set = EmbeddingSet(
            summary_embedding=summary_embedding,
            chunks=[CachedChunk(text=s.text, embedding=vec) for s, vec in pairs],
        )
        async with get_celery_session_maker()() as session:
            await EmbeddingCacheService(session).remember(key, embedding_set)
    except Exception:
        logger.warning("Embedding cache write failed; result not cached", exc_info=True)


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
