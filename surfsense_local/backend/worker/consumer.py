import logging

from huey.consumer import Consumer

from shared.db import import_models
from shared.queue import import_tasks, ingest_queue, studio_queue

# Studio jobs wait on a model: overlap them. Ingest jobs saturate the CPU: one.
# ponytail: laptop defaults; becomes a setting for power users.
STUDIO_WORKERS = 4
_QUEUES = {"ingest": (ingest_queue, 1), "studio": (studio_queue, STUDIO_WORKERS)}


def consume(name: str) -> None:
    """Drain one queue in the foreground; Electron supervises each as a sidecar."""
    queue, workers = _QUEUES[name]
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    import_models()
    import_tasks()
    logging.getLogger(__name__).info(
        "%s: worker consuming with %s threads", name, workers
    )
    Consumer(queue, workers=workers, worker_type="thread").run()
