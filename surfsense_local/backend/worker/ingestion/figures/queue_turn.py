"""The figures-only pass's turn on the one-thread ingest queue. It reads a page in
about 0.8 s, 3 s where OCR runs: once it has run some 20 s and a source's ingest
waits at the pass's own priority or above, it keeps the runs read so far and
queues itself again at that priority, behind that source. An idle pass gives
way to every upload; one someone asked for only to work queued as high, or it
would queue again ahead of what it gave way to and give way again."""

import time

from sqlalchemy import select

from modules.documents.models import Document, DocumentStatus, DocumentType
from shared.config import get_storage_settings
from shared.db import create_db_engine, create_session_factory
from worker.ingestion.queued_ingests import ingests_queued_from

__all__ = ["FiguresPassYieldedError", "FiguresTurn"]

YIELD_AFTER_SECONDS = 20.0


class FiguresPassYieldedError(Exception):
    """The pass gave the queue up: its runs are kept for the copy queued again."""


class FiguresTurn:
    def __init__(self, priority: int) -> None:
        self._priority = priority
        self._started = time.monotonic()

    def give_way(self) -> None:
        """Raises FiguresPassYieldedError once the pass has had its 20 s and an
        upload or note waits at its priority or above, a recording too."""
        if time.monotonic() - self._started < YIELD_AFTER_SECONDS:
            return
        if _source_waiting(ingests_queued_from(self._priority)):
            raise FiguresPassYieldedError


def _source_waiting(queued: set[int]) -> bool:
    if not queued:
        return False
    # No transaction is held while Docling reads, so each check opens its own.
    engine = create_db_engine(get_storage_settings().database_path)
    try:
        with create_session_factory(engine)() as session:
            pending = session.scalars(
                select(Document.id).where(
                    Document.status == DocumentStatus.PENDING,
                    Document.document_type.in_([DocumentType.FILE, DocumentType.NOTE]),
                )
            )
            # Matched here, not in SQL: a bulk copy queues more ids than SQLite binds.
            return any(document_id in queued for document_id in pending)
    finally:
        engine.dispose()
