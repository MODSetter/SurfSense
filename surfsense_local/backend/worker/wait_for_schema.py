"""Hold a worker until the API has migrated the database.

Electron starts the workers beside the API, and only the API migrates. A job
queued before an update would otherwise run against the old schema and fail.
"""

import logging
import time

from shared.config import get_storage_settings
from shared.db import create_db_engine
from shared.migrations import is_migrated

logger = logging.getLogger(__name__)

POLL_SECONDS = 0.5


def wait_for_schema() -> None:
    engine = create_db_engine(get_storage_settings().database_path)
    try:
        if not is_migrated(engine):
            logger.info("worker: waiting for the API to migrate the database")
        while not is_migrated(engine):
            time.sleep(POLL_SECONDS)
    finally:
        engine.dispose()
