"""Celery task that re-probes catalogue models for turn compatibility.

Runs weekly so a model delisted or changed upstream is blocklisted without a
deploy. Only models whose verdict has aged past ``DEFAULT_MAX_AGE_DAYS`` are
probed, so each run costs a fraction of the full catalogue.
"""

from __future__ import annotations

import asyncio
import logging

from app.celery_app import celery_app
from app.services.model_compatibility_sweep import (
    DEFAULT_MAX_AGE_DAYS,
    fetch_catalogue_model_ids,
    recently_checked_ids,
    resolve_api_key,
    sweep_models,
)

logger = logging.getLogger(__name__)


@celery_app.task(name="sweep_model_compatibility")
def sweep_model_compatibility() -> dict[str, int]:
    return asyncio.run(_sweep())


async def _sweep() -> dict[str, int]:
    api_key = resolve_api_key()
    if not api_key:
        logger.info("model compatibility sweep skipped: no OpenRouter key")
        return {}

    fresh = await recently_checked_ids(DEFAULT_MAX_AGE_DAYS)
    model_ids = [m for m in await fetch_catalogue_model_ids() if m not in fresh]
    if not model_ids:
        return {}

    counts = await sweep_models(model_ids, api_key=api_key)
    logger.info(
        "model compatibility sweep: probed %d models (%s)",
        len(model_ids),
        ", ".join(f"{status}={count}" for status, count in sorted(counts.items())),
    )
    return counts
