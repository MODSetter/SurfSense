"""The priority the running ingest job was queued at: a long Docling reading gives
way only to work queued as high, and queues again there."""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from modules.documents.tasks import PRIORITY_INTERACTIVE

__all__ = ["job_priority", "queued_at"]

# A job run outside the queue, as a test runs one, is the task's own default.
_PRIORITY: ContextVar[int] = ContextVar("ingest_priority", default=PRIORITY_INTERACTIVE)


@contextmanager
def queued_at(priority: int) -> Iterator[None]:
    token = _PRIORITY.set(priority)
    try:
        yield
    finally:
        _PRIORITY.reset(token)


def job_priority() -> int:
    return _PRIORITY.get()
