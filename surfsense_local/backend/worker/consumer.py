import logging

from huey.consumer import Consumer

from shared.db import import_models
from shared.queue import huey, import_tasks


def consume() -> None:
    """Run the consumer in the foreground; Electron supervises it as a sidecar."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    import_models()
    import_tasks()

    # Serial: ingest saturates a CPU and writes to the file the API is serving.
    Consumer(huey, workers=1).run()
