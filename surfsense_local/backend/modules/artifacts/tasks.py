from shared.queue import huey


@huey.task(retries=1)
def studio_job(artifact_id: int) -> None:
    """Generate one artifact: the model writes content, a builder renders it."""
    # Lazy: the body pulls in the builder libraries, which the API never needs.
    from worker.studio import run

    run(artifact_id)
