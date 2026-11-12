"""Settle the documents waiting on pictures from the worker, and tell open windows."""

import logging

from modules.artifacts.waiting_renders.settle import settle_waiting_renders
from shared.config import get_storage_settings
from shared.db import create_db_engine, create_session_factory
from worker.notify import notify_artifact_updates

logger = logging.getLogger(__name__)


def settle_after_job(artifact_id: int) -> None:
    """A job ended, or found its artifact gone: what waited on that picture may go.

    Never raises: the job is done, and a raise would have Huey draw it again.
    What is left waiting is settled by the sweep at the worker's next start.
    """
    try:
        _settle(picture_id=artifact_id)
    except Exception:
        logger.exception("could not settle what waited on picture %s", artifact_id)


def settle_every_waiting_render() -> None:
    """At start: a picture may have ended, or been failed as interrupted, unannounced."""
    _settle()


def _settle(picture_id: int | None = None) -> None:
    engine = create_db_engine(get_storage_settings().database_path)
    try:
        with create_session_factory(engine)() as session:
            for render in settle_waiting_renders(session, picture_id=picture_id):
                session.refresh(render)
                notify_artifact_updates(render)
    finally:
        engine.dispose()
