import logging

from huey.consumer import Consumer

from modules.documents.models import DocumentType
from modules.plugins.interrupted_runs import fail_interrupted_runs
from shared.db import import_models
from shared.queue import import_tasks, ingest_queue, plugins_queue, studio_queue
from worker.interrupted_documents import fail_interrupted_documents
from worker.wait_for_schema import wait_for_schema

# Studio jobs wait on a model: overlap them. Ingest jobs saturate the CPU: one.
# ponytail: laptop defaults; becomes a setting for power users.
STUDIO_WORKERS = 4
# Plugin runs mostly wait on the network, as Studio jobs wait on a model. This
# is the only limit on how many run at once: a fifth stays queued.
PLUGIN_WORKERS = 4
_QUEUES = {
    "ingest": (ingest_queue, 1),
    "studio": (studio_queue, STUDIO_WORKERS),
    "plugins": (plugins_queue, PLUGIN_WORKERS),
}


def consume(name: str) -> None:
    """Drain one queue in the foreground; Electron supervises each as a sidecar."""
    queue, workers = _QUEUES[name]
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    import_models()
    import_tasks()
    wait_for_schema()
    if queue is plugins_queue:
        fail_interrupted_runs()
    elif queue is ingest_queue:
        fail_interrupted_documents({DocumentType.FILE, DocumentType.NOTE})
    else:
        fail_interrupted_documents({DocumentType.ARTIFACT})
    logging.getLogger(__name__).info(
        "%s: worker consuming with %s threads", name, workers
    )
    Consumer(queue, workers=workers, worker_type="thread").run()
