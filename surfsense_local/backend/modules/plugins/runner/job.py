from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.orm import Session

from modules.plugins.models import PluginRun, PluginRunStatus
from modules.plugins.runner.declared_timeout import declared_timeout
from modules.plugins.runner.plugin_process import Stopped, run_plugin_process
from shared.config import get_storage_settings
from shared.db import create_db_engine, create_session_factory


def run(run_id: int) -> None:
    """Take one run from queued to succeeded, failed or cancelled."""
    # An engine per job, as ingest does: tests repoint the database per case.
    engine = create_db_engine(get_storage_settings().database_path)
    try:
        with create_session_factory(engine)() as session:
            if not _begin(session, run_id):
                return
            plugin_run = session.get(PluginRun, run_id)
            # Committed before the plugin starts: it writes through the API,
            # which cannot take the write lock while this transaction is open.
            session.commit()

            ended = run_plugin_process(
                plugin_run,
                declared_timeout(plugin_run),
                cancel_requested=lambda: _cancel_requested(session, plugin_run),
            )
            _record(session, plugin_run, ended.exit_code, ended.stopped)
            plugin_run.log_tail = ended.log_tail
            plugin_run.finished_at = datetime.now(UTC)
            session.commit()
    finally:
        engine.dispose()


def _begin(session: Session, run_id: int) -> bool:
    """Mark the run running unless it was cancelled while queued. False means skip."""
    started = session.execute(
        update(PluginRun)
        .where(PluginRun.id == run_id, PluginRun.status == PluginRunStatus.QUEUED)
        .values(status=PluginRunStatus.RUNNING, started_at=datetime.now(UTC))
    )
    session.commit()
    return started.rowcount == 1


def _cancel_requested(session: Session, plugin_run: PluginRun) -> bool:
    """Whether the API marked the run cancelled since the worker last looked."""
    session.refresh(plugin_run, attribute_names=["status"])
    # Let go of the write lock at once: the plugin's own writes need it.
    session.commit()
    return plugin_run.status is PluginRunStatus.CANCELLED


def _record(
    session: Session, plugin_run: PluginRun, exit_code: int, stopped: Stopped | None
) -> None:
    """Set how the run ended. A cancel that came in meanwhile wins over the exit."""
    session.refresh(plugin_run, attribute_names=["status"])
    if plugin_run.status is PluginRunStatus.CANCELLED:
        return
    if stopped is Stopped.TIMEOUT:
        plugin_run.status = PluginRunStatus.FAILED
        plugin_run.error = "timeout"
    elif exit_code == 0:
        plugin_run.status = PluginRunStatus.SUCCEEDED
    else:
        plugin_run.status = PluginRunStatus.FAILED
        plugin_run.error = f"exit {exit_code}"
