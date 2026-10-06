"""Run folders a killed worker left: each holds a script, copies of source images and a half-written file."""

import shutil

from worker.document_script.run import run_folders_root


def remove_leftover_run_folders() -> None:
    """Delete every run folder; only before the Studio worker, the one that runs scripts, takes a job."""
    shutil.rmtree(run_folders_root(), ignore_errors=True)
