import logging

from shared.queue import huey

logger = logging.getLogger(__name__)


@huey.task(retries=1)
def studio_job(artifact_id: int) -> None:
    """Generate one artifact: the model writes content, a builder renders it."""
    # Lazy: the body pulls in the builder libraries, which the API never needs.
    logger.info("studio: queue popped artifact %s", artifact_id)
    from worker.studio import run

    run(artifact_id)
