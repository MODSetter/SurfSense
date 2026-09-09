import logging

from huey.consumer import Consumer

from shared.db import import_models
from shared.queue import huey, import_tasks


def consume() -> None:
    """Run the consumer in the foreground; Electron supervises it as a sidecar."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    import_models()
    import_tasks()
    _requeue_stranded_studio_jobs()
    logging.getLogger(__name__).info("studio: worker consuming")

    # Serial: ingest saturates a CPU and writes to the file the API is serving.
    Consumer(huey, workers=1).run()


def _requeue_stranded_studio_jobs() -> None:
    """A new worker has no in-flight job; leftover processing rows are abandoned."""
    from shared.config import get_storage_settings
    from shared.db import create_db_engine, create_session_factory
    from modules.artifacts.service import enqueue_stranded_studio_jobs

    engine = create_db_engine(get_storage_settings().database_path)
    try:
        with create_session_factory(engine)() as session:
            enqueue_stranded_studio_jobs(session, include_processing=True)
    finally:
        engine.dispose()
