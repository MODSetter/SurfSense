"""Decode a recording in the worker's own binary, started as a child, and wait
for it while the job keeps checking whether it was cancelled."""

import logging
import subprocess
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import IO

from worker.audio_decode.outcome import DecodeOutcome

__all__ = ["decode_in_child"]

logger = logging.getLogger(__name__)

POLL_SECONDS = 1.0
# How long its last words are still read once it has exited.
_LAST_OUTPUT_SECONDS = 5.0
# What of a dead decoder's output reaches the log.
_TAIL_CHARS = 2000
_WORKER_ENTRY = Path(__file__).resolve().parents[2] / "worker.py"
# A packaged worker may have no console; the child must not open one.
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def decode_in_child(
    source: Path, out: Path, *, between_polls: Callable[[], None]
) -> DecodeOutcome:
    """`out` holds the whole recording once this answers `decoded`, and is
    absent otherwise. `between_polls` runs about every second while the child
    works: whatever it raises stops the child and is raised here."""
    process = subprocess.Popen(
        _command(source, out),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        creationflags=_NO_WINDOW,
    )
    printed = _Printed(process.stdout)
    try:
        exit_code = _wait(process, between_polls)
    except BaseException:
        process.kill()
        process.wait()
        _remove(out)
        raise
    finally:
        # The child exits when this closes, should it still be running.
        process.stdin.close()
    said = printed.text()
    outcome = _outcome(said)
    if exit_code == 0 and outcome is not None:
        return outcome
    _remove(out)
    logger.warning(
        "transcription: the decoder exited with %s: %s", exit_code, said[-_TAIL_CHARS:]
    )
    return DecodeOutcome("undecodable", detail=f"the decoder exited with {exit_code}")


def _command(source: Path, out: Path) -> list[str]:
    """The worker in decode mode: its own binary when packaged, else worker.py."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--decode-audio", str(source), str(out)]
    return [
        sys.executable,
        str(_WORKER_ENTRY),
        "--decode-audio",
        str(source),
        str(out),
    ]


def _wait(process: subprocess.Popen, between_polls: Callable[[], None]) -> int:
    while True:
        try:
            return process.wait(timeout=POLL_SECONDS)
        except subprocess.TimeoutExpired:
            between_polls()


def _outcome(said: str) -> DecodeOutcome | None:
    lines = said.strip().splitlines()
    try:
        return DecodeOutcome.from_line(lines[-1]) if lines else None
    except (ValueError, TypeError):
        return None


def _remove(out: Path) -> None:
    out.unlink(missing_ok=True)
    out.with_name(f"{out.name}.part").unlink(missing_ok=True)


class _Printed:
    """Read on a thread, so a decoder that prints much never blocks on the pipe."""

    def __init__(self, pipe: IO[bytes]) -> None:
        self._said = b""
        self._thread = threading.Thread(target=self._read, args=(pipe,), daemon=True)
        self._thread.start()

    def _read(self, pipe: IO[bytes]) -> None:
        with pipe:
            self._said = pipe.read()

    def text(self) -> str:
        self._thread.join(_LAST_OUTPUT_SECONDS)
        return self._said.decode(errors="replace")
