"""The figures-only pass's turn on the one-thread ingest queue. Nobody waits on
it, and it reads a page in about 0.8 s, 3 s where OCR runs: once it has run some
20 s and any source waits, it keeps the runs read so far and queues itself again
at the priority it came with, behind that source."""

import time

from sqlalchemy import exists, select

from modules.documents.models import Document, DocumentStatus, DocumentType
from shared.config import get_storage_settings
from shared.db import create_db_engine, create_session_factory

__all__ = ["FiguresPassYieldedError", "FiguresTurn"]

YIELD_AFTER_SECONDS = 20.0


class FiguresPassYieldedError(Exception):
    """The pass gave the queue up: its runs are kept for the copy queued again."""


class FiguresTurn:
    def __init__(self) -> None:
        self._started = time.monotonic()

    def give_way(self) -> None:
        """Raises FiguresPassYieldedError once the pass has had its 20 s and any
        upload or note waits, a recording too."""
        if time.monotonic() - self._started < YIELD_AFTER_SECONDS:
            return
        if _any_source_pending():
            raise FiguresPassYieldedError


def _any_source_pending() -> bool:
    # No transaction is held while Docling reads, so each check opens its own.
    engine = create_db_engine(get_storage_settings().database_path)
    try:
        with create_session_factory(engine)() as session:
            return bool(
                session.scalar(
                    select(
                        exists().where(
                            Document.status == DocumentStatus.PENDING,
                            Document.document_type.in_(
                                [DocumentType.FILE, DocumentType.NOTE]
                            ),
                        )
                    )
                )
            )
    finally:
        engine.dispose()
