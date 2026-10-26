import logging

from huey.consumer import Consumer

from modules.documents.models import DocumentType
from modules.plugins.bundles.interrupted_runs import fail_interrupted_runs
from shared.db import import_models
from shared.queue import import_tasks, ingest_queue, plugins_queue, studio_queue
from worker.document_script.leftover_run_folders import remove_leftover_run_folders
from worker.interrupted_documents import fail_interrupted_documents
from worker.interrupted_pulls import fail_interrupted_pulls
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
# Longest wait between polls of an idle queue. Huey's default backs off to 10 s,
# which an idle ingest worker took to notice an upload that is ready in about a
# second once read; a poll is one query on huey.db, its own file.
MAX_IDLE_POLL_SECONDS = {"ingest": 0.5, "studio": 1.0, "plugins": 1.0}


def consume(name: str) -> None:
    """Drain one queue in the foreground; Electron supervises each as a sidecar."""
    queue, workers = _QUEUES[name]
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    import_models()
    import_tasks()
    wait_for_schema()
    if queue is plugins_queue:
        fail_interrupted_runs()
        fail_interrupted_pulls()
    elif queue is ingest_queue:
        fail_interrupted_documents({DocumentType.FILE, DocumentType.NOTE})
    else:
        # No script runs yet, so every run folder is one a killed worker left.
        remove_leftover_run_folders()
        fail_interrupted_documents({DocumentType.ARTIFACT})
    logging.getLogger(__name__).info(
        "%s: worker consuming with %s threads", name, workers
    )
    Consumer(
        queue,
        workers=workers,
        worker_type="thread",
        max_delay=MAX_IDLE_POLL_SECONDS[name],
    ).run()
