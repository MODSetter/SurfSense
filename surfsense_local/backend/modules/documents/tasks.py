from shared.queue import huey


@huey.task(retries=2)
def ingest_document(document_id: int) -> None:
    """Parse, chunk, embed and index one document.

    Declared here because the API enqueues it and the worker runs it, and Huey
    binds a task to its queue at decoration. The body belongs to the worker
    workstream; nothing consumes this queue yet, so uploads sit at pending.
    """
    raise NotImplementedError("worker/02-ingest.md")
