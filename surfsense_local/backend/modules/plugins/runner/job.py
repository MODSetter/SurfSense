from datetime import UTC, datetime

from modules.plugins.models import PluginRun, PluginRunStatus
from modules.plugins.runner.plugin_process import run_plugin_process
from shared.config import get_storage_settings
from shared.db import create_db_engine, create_session_factory


def run(run_id: int) -> None:
    """Take one run from queued to succeeded or failed."""
    # An engine per job, as ingest does: tests repoint the database per case.
    engine = create_db_engine(get_storage_settings().database_path)
    try:
        with create_session_factory(engine)() as session:
            plugin_run = session.get(PluginRun, run_id)
            plugin_run.status = PluginRunStatus.RUNNING
            plugin_run.started_at = datetime.now(UTC)
            # Committed before the plugin starts: it writes through the API,
            # which cannot take the write lock while this transaction is open.
            session.commit()

            ended = run_plugin_process(plugin_run)

            if ended.exit_code == 0:
                plugin_run.status = PluginRunStatus.SUCCEEDED
            else:
                plugin_run.status = PluginRunStatus.FAILED
                plugin_run.error = f"exit {ended.exit_code}"
            plugin_run.log_tail = ended.log_tail
            plugin_run.finished_at = datetime.now(UTC)
            session.commit()
    finally:
        engine.dispose()
