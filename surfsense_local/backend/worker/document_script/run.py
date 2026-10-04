"""Run a model-written document script in its own process and read back its file.

A process, not a thread: only a process can be stopped at its time limit (ADR 0039).
"""

import logging
import shutil
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from shared import cancellation
from shared.config import get_storage_settings
from worker.document_script.child_environment import child_environment
from worker.document_script.kill_process_tree import process_tree
from worker.document_script.run_folder import prepare_run_folder, require_plain_name

logger = logging.getLogger(__name__)

TRACEBACK_LINES = 30
# How long output is still read after the tree is killed: a process that
# escaped it (POSIX: one that left the group) can hold the pipe open for good.
LAST_OUTPUT_SECONDS = 5
# How soon a cancelled job stops its script.
CANCEL_POLL_SECONDS = 1.0
_WORKER_ENTRY = Path(__file__).resolve().parents[2] / "worker.py"


@dataclass(frozen=True)
class ScriptResult:
    """What one run produced, or the one line and traceback that say why not."""

    ok: bool
    output: bytes | None
    error: str | None
    traceback_tail: str | None
    seconds: float


def run_document_script(
    script: str,
    *,
    output_name: str,
    images: dict[str, Path],
    timeout_seconds: float = 120,
) -> ScriptResult:
    """Run the script with OUTPUT_PATH=<folder>/<output_name> and images at
    IMAGES_DIR/<name>.png, then remove the folder. The caller keeps the script.

    A cancelled job (shared.cancellation) kills the script and raises its error.
    """
    require_plain_name(output_name, *images)
    root = get_storage_settings().data_dir / "tmp" / "document-scripts"
    folder = root / uuid.uuid4().hex
    try:
        prepare_run_folder(folder, script, images)
        started = time.monotonic()
        exit_code, stderr = _run_child(folder, output_name, timeout_seconds)
        seconds = time.monotonic() - started
        if exit_code is None:
            logger.info("document script: timed out after %ss", timeout_seconds)
            return _failed(f"timed out after {timeout_seconds:g} s", stderr, seconds)
        if exit_code != 0:
            return _failed(_error_line(exit_code, stderr), stderr, seconds)
        return _read_output(folder / output_name, stderr, seconds)
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def _run_child(
    folder: Path, output_name: str, timeout_seconds: float
) -> tuple[int | None, str]:
    """The child's exit code, None when it was killed at the limit, and its stderr.

    The run ends when the script's process does; whatever it left running is
    killed then, not waited for.
    """
    command = _child_command(folder)
    with process_tree(command, child_environment(folder, output_name)) as process:
        stderr = _StderrReader(process.stderr)
        exit_code = _wait_for_exit(process, timeout_seconds)
    return exit_code, stderr.text(timeout_seconds=LAST_OUTPUT_SECONDS)


def _wait_for_exit(process: subprocess.Popen, timeout_seconds: float) -> int | None:
    deadline = time.monotonic() + timeout_seconds
    while (remaining := deadline - time.monotonic()) > 0:
        try:
            return process.wait(timeout=min(CANCEL_POLL_SECONDS, remaining))
        except subprocess.TimeoutExpired:
            cancellation.raise_if_cancelled()
    return None


class _StderrReader:
    """Reads the pipe on a thread, so waiting is on the process, not on the pipe:
    a helper the script started may hold the pipe open after the script exits."""

    def __init__(self, pipe: IO[bytes]) -> None:
        self._chunks: list[bytes] = []
        self._thread = threading.Thread(target=self._read, args=(pipe,), daemon=True)
        self._thread.start()

    def _read(self, pipe: IO[bytes]) -> None:
        with pipe:
            while chunk := pipe.read1(65536):
                self._chunks.append(chunk)

    def text(self, timeout_seconds: float) -> str:
        self._thread.join(timeout_seconds)
        return b"".join(self._chunks).decode(errors="replace")


def _child_command(folder: Path) -> list[str]:
    """The worker in script mode: its own binary when packaged, else worker.py."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--run-document-script", str(folder)]
    return [sys.executable, str(_WORKER_ENTRY), "--run-document-script", str(folder)]


def _read_output(path: Path, stderr: str, seconds: float) -> ScriptResult:
    if not path.is_file():
        return _failed("the script wrote no file at OUTPUT_PATH", stderr, seconds)
    output = path.read_bytes()
    if not output:
        return _failed("the script wrote an empty file at OUTPUT_PATH", stderr, seconds)
    return ScriptResult(
        ok=True, output=output, error=None, traceback_tail=None, seconds=seconds
    )


def _error_line(exit_code: int, stderr: str) -> str:
    """The exception line a traceback ends with, or the status when nothing printed."""
    lines = stderr.strip().splitlines()
    return lines[-1] if lines else f"the script exited with status {exit_code}"


def _failed(error: str, stderr: str, seconds: float) -> ScriptResult:
    tail = "\n".join(stderr.strip().splitlines()[-TRACEBACK_LINES:])
    return ScriptResult(
        ok=False, output=None, error=error, traceback_tail=tail or None, seconds=seconds
    )
