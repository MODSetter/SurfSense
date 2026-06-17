import contextlib
import logging
import time
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import set_committed_value

from app.db import Chunk, Document, DocumentStatus

logger = logging.getLogger(__name__)


async def rollback_and_persist_failure(
    session: AsyncSession, document: Document, message: str
) -> None:
    """Roll back the current transaction and best-effort persist a failed status.

    Called exclusively from except blocks — must never raise, or the new exception
    would chain with the original and mask it entirely.
    """
    try:
        await session.rollback()
    except Exception:
        logger.warning(
            "Rollback failed; cannot persist failed status for document %s",
            getattr(document, "id", "unknown"),
            exc_info=True,
        )
        return
    try:
        await session.refresh(document)
        document.updated_at = datetime.now(UTC)
        document.status = DocumentStatus.failed(message)
        await session.commit()
    except Exception:
        logger.warning(
            "Could not persist failed status for document %s; will retry next sync",
            getattr(document, "id", "unknown"),
            exc_info=True,
        )
        with contextlib.suppress(Exception):
            await session.rollback()


async def persist_scratch_index(
    session: AsyncSession,
    document: Document,
    content: str,
    chunks: list[Chunk],
    *,
    batch_size: int,
    perf: logging.Logger,
) -> None:
    """Commit document content first, then chunk rows in batches, then mark ready."""
    if document.id is None:
        raise ValueError("document.id is required to persist chunks")

    document.content = content
    document.updated_at = datetime.now(UTC)
    await session.commit()

    t_persist = time.perf_counter()
    total = len(chunks)
    if total == 0:
        set_committed_value(document, "chunks", [])
        document.status = DocumentStatus.ready()
        document.updated_at = datetime.now(UTC)
        await session.commit()
        return

    effective_batch = total if batch_size <= 0 else batch_size
    num_batches = (total + effective_batch - 1) // effective_batch
    doc_id = document.id

    for batch_idx, start in enumerate(range(0, total, effective_batch), start=1):
        batch = chunks[start : start + effective_batch]
        t_batch = time.perf_counter()
        for chunk in batch:
            chunk.document_id = doc_id
        session.add_all(batch)
        await session.commit()
        perf.info(
            "[indexing] chunk batch doc=%d batch=%d/%d rows=%d in %.3fs",
            doc_id,
            batch_idx,
            num_batches,
            len(batch),
            time.perf_counter() - t_batch,
        )

    set_committed_value(document, "chunks", chunks)
    document.status = DocumentStatus.ready()
    document.updated_at = datetime.now(UTC)
    await session.commit()
    perf.info(
        "[indexing] chunk persist doc=%d chunks=%d batches=%d in %.3fs",
        doc_id,
        total,
        num_batches,
        time.perf_counter() - t_persist,
    )
