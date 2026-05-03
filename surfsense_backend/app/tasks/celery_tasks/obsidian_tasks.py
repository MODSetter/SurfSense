"""Celery tasks for Obsidian plugin background processing."""

from __future__ import annotations

import logging

from app.celery_app import celery_app
from app.db import SearchSourceConnector
from app.schemas.obsidian_plugin import NotePayload
from app.services.obsidian_plugin_indexer import upsert_note
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task

logger = logging.getLogger(__name__)


@celery_app.task(name="index_obsidian_attachment", bind=True)
def index_obsidian_attachment_task(
    self,
    connector_id: int,
    payload_data: dict,
    user_id: str,
) -> None:
    """Process one Obsidian non-markdown attachment asynchronously."""
    return run_async_celery_task(
        lambda: _index_obsidian_attachment(
            connector_id=connector_id,
            payload_data=payload_data,
            user_id=user_id,
        )
    )


async def _index_obsidian_attachment(
    *,
    connector_id: int,
    payload_data: dict,
    user_id: str,
) -> None:
    async with get_celery_session_maker()() as session:
        connector = await session.get(SearchSourceConnector, connector_id)
        if connector is None:
            logger.warning(
                "obsidian attachment task skipped: connector %s not found", connector_id
            )
            return

        payload = NotePayload.model_validate(payload_data)
        await upsert_note(
            session,
            connector=connector,
            payload=payload,
            user_id=user_id,
        )
