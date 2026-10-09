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
from worker.document_script.run_folder import (
    IMAGES_FOLDER,
    prepare_run_folder,
    require_plain_name,
)

logger = logging.getLogger(__name__)

TRACEBACK_LINES = 30
# Room for the error line and TRACEBACK_LINES of long traceback lines.
STDERR_TAIL_BYTES = 64 * 1024
# What an analysis prints is its result; past this it is a frame printed whole.
STDOUT_HEAD_BYTES = 64 * 1024
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


@dataclass(frozen=True)
class ChildRun:
    """How one script's process ended: its exit code, None when killed at the
    limit, the start of what it printed and the end of its stderr."""

    exit_code: int | None
    stdout: str
    # Bytes printed past the kept start.
    stdout_cut: int
    stderr: str
    seconds: float


def run_document_script(
    script: str,
    *,
    output_name: str,
    images: dict[str, Path],
    template: Path | None = None,
    timeout_seconds: float = 120,
) -> ScriptResult:
    """Run the script with OUTPUT_PATH=<folder>/<output_name>, images at
    IMAGES_DIR/<name>.png and a copy of `template` at TEMPLATE_PATH, then remove
    the folder. The caller keeps the script.

    A cancelled job (shared.cancellation) kills the script and raises its error.
    """
    require_plain_name(output_name, *images)
    folder = run_folders_root() / uuid.uuid4().hex
    try:
        template_name = prepare_run_folder(folder, script, images, template)
        contract = {
            "OUTPUT_PATH": str(folder / output_name),
            "IMAGES_DIR": str(folder / IMAGES_FOLDER),
        }
        if template_name is not None:
            contract["TEMPLATE_PATH"] = str(folder / template_name)
        child = run_child(folder, contract, timeout_seconds)
        stderr, seconds = child.stderr, child.seconds
        if child.exit_code is None:
            return _failed(f"timed out after {timeout_seconds:g} s", stderr, seconds)
        if child.exit_code != 0:
            return _failed(error_line(child.exit_code, stderr), stderr, seconds)
        return _read_output(folder / output_name, stderr, seconds)
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def run_folders_root() -> Path:
    """Where each run gets its own folder."""
    return get_storage_settings().data_dir / "tmp" / "document-scripts"


def run_child(
    folder: Path, contract: dict[str, str], timeout_seconds: float
) -> ChildRun:
    """Run the folder's script.py with `contract` in its environment.

    The run ends when the script's process does; whatever it left running is
    killed then, not waited for. A cancelled job raises its error.
    """
    command = _child_command(folder)
    environment = child_environment(folder, contract)
    started = time.monotonic()
    with process_tree(command, environment, stdout=subprocess.PIPE) as process:
        stdout = _PipeReader(process.stdout, STDOUT_HEAD_BYTES, keep_start=True)
        stderr = _PipeReader(process.stderr, STDERR_TAIL_BYTES, keep_start=False)
        exit_code = _wait_for_exit(process, timeout_seconds)
    seconds = time.monotonic() - started
    if exit_code is None:
        logger.info("script: timed out after %ss", timeout_seconds)
    # Windows prints line ends as CRLF in text mode.
    printed = stdout.text(timeout_seconds=LAST_OUTPUT_SECONDS)
    return ChildRun(
        exit_code=exit_code,
        stdout=printed.replace("\r\n", "\n"),
        stdout_cut=stdout.dropped,
        stderr=stderr.text(timeout_seconds=LAST_OUTPUT_SECONDS),
        seconds=seconds,
    )


def _wait_for_exit(process: subprocess.Popen, timeout_seconds: float) -> int | None:
    deadline = time.monotonic() + timeout_seconds
    while (remaining := deadline - time.monotonic()) > 0:
        try:
            return process.wait(timeout=min(CANCEL_POLL_SECONDS, remaining))
        except subprocess.TimeoutExpired:
            cancellation.raise_if_cancelled()
    return None


class _PipeReader:
    """Reads the pipe on a thread, so waiting is on the process, not on the pipe:
    a helper the script started may hold the pipe open after the script exits.

    Keeps only `limit` bytes, its start or its end: a runaway script can write
    gigabytes in its two minutes. The pipe is drained either way, or the script
    would block once it is full.
    """

    def __init__(self, pipe: IO[bytes], limit: int, *, keep_start: bool) -> None:
        self._kept = bytearray()
        self._limit = limit
        self._keep_start = keep_start
        self.dropped = 0
        self._thread = threading.Thread(target=self._read, args=(pipe,), daemon=True)
        self._thread.start()

    def _read(self, pipe: IO[bytes]) -> None:
        with pipe:
            while chunk := pipe.read1(65536):
                self._kept += chunk
                over = len(self._kept) - self._limit
                if over > 0:
                    self.dropped += over
                    if self._keep_start:
                        del self._kept[self._limit :]
                    else:
                        del self._kept[:over]

    def text(self, timeout_seconds: float) -> str:
        self._thread.join(timeout_seconds)
        return bytes(self._kept).decode(errors="replace")


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


def error_line(exit_code: int, stderr: str) -> str:
    """The exception line a traceback ends with, or the status when nothing printed."""
    lines = stderr.strip().splitlines()
    return lines[-1] if lines else f"the script exited with status {exit_code}"


def traceback_tail(stderr: str) -> str | None:
    """The last TRACEBACK_LINES of stderr: they name the script's failing line."""
    return "\n".join(stderr.strip().splitlines()[-TRACEBACK_LINES:]) or None


def _failed(error: str, stderr: str, seconds: float) -> ScriptResult:
    return ScriptResult(
        ok=False,
        output=None,
        error=error,
        traceback_tail=traceback_tail(stderr),
        seconds=seconds,
    )
