"""The analysis job: the Studio worker runs the script, since the packaged worker is the binary that ships pandas (ADR 0039)."""

from pathlib import Path

from shared.queue import studio_queue
from worker.document_script.analysis_run import (
    AnalysisInput,
    AnalysisRun,
    run_analysis_script,
)

# Ahead of Studio's own jobs: a turn is waiting on this one.
PRIORITY = 100
SCRIPT_SECONDS = 120
# Started later than this, it could not finish inside the tool call waiting for
# it, so it is dropped instead of run unseen.
START_WITHIN_SECONDS = 60


@studio_queue.task(priority=PRIORITY, expires=START_WITHIN_SECONDS)
def analyse_data(script: str, inputs: list[AnalysisInput], keep_in: str) -> AnalysisRun:
    """Run one analysis and keep its tables and charts in keep_in."""
    return run_analysis_script(
        script, inputs, Path(keep_in), timeout_seconds=SCRIPT_SECONDS
    )
