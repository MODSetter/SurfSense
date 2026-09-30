from datetime import UTC, datetime

from sqlalchemy.orm import Session

from modules.plugins.models import PluginRun, PluginRunStatus
from shared.queue import plugins_queue, revoke_pending


def cancel_plugin_run(session: Session, run: PluginRun) -> bool:
    """Stop a run the user no longer wants. False when it had already ended.

    A queued run ends here and never starts. A running one is marked, and the
    worker stops its plugin within a second of seeing the mark.
    """
    if run.status is PluginRunStatus.QUEUED:
        run.status = PluginRunStatus.CANCELLED
        run.finished_at = datetime.now(UTC)
        session.commit()
        revoke_pending(plugins_queue, "run_plugin", run.id)
        return True
    if run.status is PluginRunStatus.RUNNING:
        run.status = PluginRunStatus.CANCELLED
        session.commit()
        return True
    return False
