"""Celery task pruning abandoned knowledge-store working copies."""

from __future__ import annotations

import asyncio
import logging

from app.celery_app import celery_app
from app.knowledge_store.janitor import prune_abandoned_working_copies
from app.knowledge_store.settings import load_knowledge_store_settings

logger = logging.getLogger(__name__)


@celery_app.task(name="prune_knowledge_store_working_copies")
def prune_knowledge_store_working_copies() -> int:
    if not load_knowledge_store_settings().enabled:
        return 0
    pruned = asyncio.run(prune_abandoned_working_copies())
    total = sum(len(ids) for ids in pruned.values())
    if pruned:
        logger.info("Pruned %d abandoned working copies: %s", total, pruned)
    return total
