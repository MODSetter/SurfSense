"""Queueing the figures-only pass for a source: once per priority."""

from modules.documents.tasks import extract_figures
from shared.queue import ingest_queue


def queue_figures_pass(document_id: int, priority: int) -> None:
    """Not again while a copy waits: the pass reads the whole file, and callers
    poll. A copy at a lower priority does not count, or someone asking would
    wait behind the bulk copy ingest queued."""
    wanted = extract_figures.s(document_id, priority=priority)
    waiting = any(
        task.name == wanted.name
        and task.args == wanted.args
        and (task.priority or 0) >= priority
        for task in ingest_queue.pending()
    )
    if not waiting:
        ingest_queue.enqueue(wanted)
