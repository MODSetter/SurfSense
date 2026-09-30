from datetime import UTC, datetime

import psutil
from sqlalchemy import and_, or_, select

from modules.plugins.models import PluginRun, PluginRunStatus
from shared.config import get_storage_settings
from shared.db import create_db_engine, create_session_factory
from shared.queue import plugins_queue, revoke_pending


def fail_interrupted_runs() -> None:
    """Fail the runs a worker left queued or running when the app quit.

    Called before this worker takes its first job. So every running run is a
    previous worker's, and its plugin stopped with it. A queued run created
    after this worker started is the user's, and is left for it to run.
    """
    started = datetime.fromtimestamp(psutil.Process().create_time(), UTC)
    engine = create_db_engine(get_storage_settings().database_path)
    try:
        with create_session_factory(engine)() as session:
            interrupted = session.scalars(
                select(PluginRun).where(
                    or_(
                        PluginRun.status == PluginRunStatus.RUNNING,
                        and_(
                            PluginRun.status == PluginRunStatus.QUEUED,
                            PluginRun.created_at < started,
                        ),
                    )
                )
            ).all()
            for run in interrupted:
                run.status = PluginRunStatus.FAILED
                run.error = "interrupted"
                run.finished_at = datetime.now(UTC)
            session.commit()
            for run in interrupted:
                revoke_pending(plugins_queue, "run_plugin", run.id)
    finally:
        engine.dispose()
