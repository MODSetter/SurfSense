"""Entry point: serve ETL parses from cache, parsing only on a miss."""

from __future__ import annotations

import asyncio
import hashlib
import logging

from app.config import config
from app.etl_pipeline.cache.schemas import ParseKey
from app.etl_pipeline.cache.service import EtlCacheService
from app.etl_pipeline.cache.settings import load_etl_cache_settings
from app.etl_pipeline.etl_document import EtlRequest, EtlResult
from app.etl_pipeline.etl_pipeline_service import EtlPipelineService
from app.etl_pipeline.file_classifier import FileCategory, classify_file

logger = logging.getLogger(__name__)

_HASH_CHUNK = 1024 * 1024


async def extract_with_cache(
    request: EtlRequest, *, vision_llm=None
) -> EtlResult:
    """Drop-in for ``EtlPipelineService.extract`` that reuses prior parser output."""
    settings = load_etl_cache_settings()

    # Vision-LLM appends model-generated content not captured by the key, so its
    # output must not be shared with plain parses (and vice versa): bypass cache.
    cacheable = (
        settings.enabled
        and vision_llm is None
        and bool(config.ETL_SERVICE)
        and classify_file(request.filename) == FileCategory.DOCUMENT
    )
    if not cacheable:
        return await EtlPipelineService(vision_llm=vision_llm).extract(request)

    key = ParseKey.for_document(
        await asyncio.to_thread(_hash_file, request.file_path),
        etl_service=config.ETL_SERVICE,
        mode=request.processing_mode.value,
        version=settings.parser_version,
    )

    cached_result = await _recall(key)
    if cached_result is not None:
        return cached_result

    result = await EtlPipelineService(vision_llm=vision_llm).extract(request)
    await _remember(key, result)
    return result


async def _recall(key: ParseKey) -> EtlResult | None:
    # Caching is best-effort: any failure falls through to a normal parse.
    try:
        from app.tasks.celery_tasks import get_celery_session_maker

        async with get_celery_session_maker()() as session:
            return await EtlCacheService(session).recall(key)
    except Exception:
        logger.warning("ETL cache recall failed; parsing fresh", exc_info=True)
        return None


async def _remember(key: ParseKey, result: EtlResult) -> None:
    try:
        from app.tasks.celery_tasks import get_celery_session_maker

        async with get_celery_session_maker()() as session:
            await EtlCacheService(session).remember(key, result)
    except Exception:
        logger.warning("ETL cache write failed; result not cached", exc_info=True)


def _hash_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(_HASH_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()
