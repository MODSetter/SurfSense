import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.plugins.bundles.cancel_run import cancel_plugin_run
from modules.plugins.bundles.models import PluginRun, PluginRunStatus

# Enough for the worker to see a cancel (a second) and for a plugin to be asked
# to stop, then killed (five more). A run still going after that has no worker.
STOP_WAIT_SECONDS = 10


def stop_workspace_runs(session: Session, workspace_id: int) -> None:
    """Cancel the workspace's runs and wait until their plugins have stopped.

    Deleting a workspace under a running plugin would refuse its next write,
    and fail the run for a reason that has nothing to do with the plugin.
    """
    active = session.scalars(
        select(PluginRun).where(
            PluginRun.workspace_id == workspace_id,
            PluginRun.status.in_((PluginRunStatus.QUEUED, PluginRunStatus.RUNNING)),
        )
    ).all()
    for run in active:
        cancel_plugin_run(session, run)

    deadline = time.monotonic() + STOP_WAIT_SECONDS
    while time.monotonic() < deadline:
        for run in active:
            session.refresh(run, attribute_names=["finished_at"])
        # The worker needs the write lock to record that a run stopped.
        session.commit()
        if all(run.finished_at is not None for run in active):
            return
        time.sleep(0.1)
