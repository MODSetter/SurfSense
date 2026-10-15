"""Run a model-written analysis script over copies of spreadsheets and CSVs, and keep the tables and charts it saves.

The same runner as a document script (ADR 0039): its own process, its time
limit, an environment without secrets.
"""

import uuid
from dataclasses import dataclass
from pathlib import Path

from worker.document_script.analysis_folder import (
    INPUT_FOLDER,
    OUTPUT_FOLDER,
    AnalysisInput,
    prepare_analysis_folder,
    remove_analysis_folder,
)
from worker.document_script.kept_outputs import keep_outputs
from worker.document_script.run import (
    error_line,
    run_child,
    run_folders_root,
    traceback_tail,
)

__all__ = ["AnalysisInput", "AnalysisRun", "run_analysis_script"]


@dataclass(frozen=True)
class AnalysisRun:
    """What the script printed and the files kept from it, or why it failed."""

    ok: bool
    stdout: str
    # Bytes printed past the kept start.
    stdout_cut: int
    error: str | None
    traceback_tail: str | None
    kept: tuple[str, ...]
    left_out: tuple[str, ...]
    seconds: float


def run_analysis_script(
    script: str,
    inputs: list[AnalysisInput],
    keep_in: Path,
    *,
    timeout_seconds: float = 120,
) -> AnalysisRun:
    """Run the script with INPUT_DIR holding the inputs and OUTPUT_DIR empty; on
    success move what it saved there into keep_in. A failure keeps nothing."""
    folder = run_folders_root() / uuid.uuid4().hex
    try:
        prepare_analysis_folder(folder, script, inputs)
        contract = {
            "INPUT_DIR": str(folder / INPUT_FOLDER),
            "OUTPUT_DIR": str(folder / OUTPUT_FOLDER),
        }
        child = run_child(folder, contract, timeout_seconds)
        failed = None
        if child.exit_code is None:
            failed = f"timed out after {timeout_seconds:g} s"
        elif child.exit_code != 0:
            failed = error_line(child.exit_code, child.stderr)
        if failed is not None:
            return AnalysisRun(
                ok=False,
                stdout=child.stdout,
                stdout_cut=child.stdout_cut,
                error=failed,
                traceback_tail=traceback_tail(child.stderr),
                kept=(),
                left_out=(),
                seconds=child.seconds,
            )
        outputs = keep_outputs(folder / OUTPUT_FOLDER, keep_in)
        return AnalysisRun(
            ok=True,
            stdout=child.stdout,
            stdout_cut=child.stdout_cut,
            error=None,
            traceback_tail=None,
            kept=outputs.kept,
            left_out=outputs.left_out,
            seconds=child.seconds,
        )
    finally:
        remove_analysis_folder(folder)
