"""Celery task that prunes the embedding cache by TTL, then by size budget."""

from __future__ import annotations

import contextlib
import logging
from datetime import UTC, datetime, timedelta

from app.celery_app import celery_app
from app.etl_pipeline.cache.eviction.policy import select_over_budget
from app.etl_pipeline.cache.schemas import EvictionCandidate
from app.indexing_pipeline.cache.persistence import CachedEmbeddingSetRepository
from app.indexing_pipeline.cache.settings import load_embedding_cache_settings
from app.indexing_pipeline.cache.storage import EmbeddingCacheStore
from app.observability import metrics
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task

logger = logging.getLogger(__name__)


@celery_app.task(name="evict_embedding_cache")
def evict_embedding_cache_task():
    return run_async_celery_task(_evict)


async def _evict() -> None:
    """Expire stale entries, then shed the coldest overflow only if still over budget."""
    settings = load_embedding_cache_settings()
    if not settings.enabled:
        return

    store = EmbeddingCacheStore()
    async with get_celery_session_maker()() as session:
        index = CachedEmbeddingSetRepository(session)

        cutoff = datetime.now(UTC) - timedelta(days=settings.ttl_days)
        expired = await index.select_expired(
            cutoff=cutoff, limit=settings.eviction_batch
        )
        await _drop(index, store, expired, phase="ttl")

        total = await index.total_size_bytes()
        if total > settings.max_total_bytes:
            coldest = await index.select_coldest(limit=settings.eviction_batch)
            over_budget = select_over_budget(
                coldest,
                current_total_bytes=total,
                max_total_bytes=settings.max_total_bytes,
            )
            await _drop(index, store, over_budget, phase="size")


async def _drop(
    index: CachedEmbeddingSetRepository,
    store: EmbeddingCacheStore,
    candidates: list[EvictionCandidate],
    *,
    phase: str,
) -> None:
    if not candidates:
        return
    for candidate in candidates:
        # Drop the index row even if the blob delete fails (orphan blob is harmless).
        with contextlib.suppress(Exception):
            await store.delete(candidate.storage_key)
    await index.delete_by_ids([candidate.id for candidate in candidates])
    metrics.record_embedding_cache_eviction(len(candidates), phase=phase)
    logger.info("Evicted %d cached embedding sets (%s)", len(candidates), phase)
