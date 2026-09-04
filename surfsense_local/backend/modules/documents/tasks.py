from shared.queue import huey


@huey.task(retries=2)
def ingest_document(document_id: int) -> None:
    """Parse, chunk, embed and index one document.

    Lives with the API that enqueues it, since Huey binds a task to its queue
    at decoration.
    """
    raise NotImplementedError("worker/02-ingest.md")
