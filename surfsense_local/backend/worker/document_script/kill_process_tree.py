"""A script's process and everything it starts, bound so all of it can be killed.

Bound when the process starts, not found later by walking its children: a
helper whose parent has exited is no one's child, so a walk misses it. Windows
holds the tree in a job object; POSIX in the script's own process group.
"""

import os
import signal
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager, suppress

import psutil

# How long the killed processes get to end before the run moves on.
REAP_SECONDS = 5
# A packaged worker may have no console; the script must not open one.
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
_SUSPENDED = 0x4  # CREATE_SUSPENDED: nothing runs before the job holds it


@contextmanager
def process_tree(command: list[str], env: dict[str, str]) -> Iterator[subprocess.Popen]:
    """Start the command with its stdout and stderr piped; leaving kills all that is left of it."""
    if sys.platform == "win32":
        with _in_a_job(command, env) as process:
            yield process
    else:
        with _in_a_process_group(command, env) as process:
            yield process


@contextmanager
def _in_a_job(command: list[str], env: dict[str, str]) -> Iterator[subprocess.Popen]:
    from worker.document_script.windows_job import KillOnCloseJob

    job = KillOnCloseJob()
    try:
        process = subprocess.Popen(
            command,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=_NO_WINDOW | _SUSPENDED,
        )
        try:
            job.assign(process.pid)
            psutil.Process(process.pid).resume()
            yield process
        finally:
            process.kill()  # in case it never joined the job
            job.kill(REAP_SECONDS)
            _reap(process)
    finally:
        # Closing its last handle also kills what is left, as when the worker dies.
        job.close()


@contextmanager
def _in_a_process_group(
    command: list[str], env: dict[str, str]
) -> Iterator[subprocess.Popen]:
    # Its own group, which a stop of the worker's group does not reach; the
    # child kills its group when the worker's end of stdin closes (child.py).
    process = subprocess.Popen(
        command,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        process_group=0,
    )
    try:
        yield process
    finally:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        _reap(process)
        process.stdin.close()


def _reap(process: subprocess.Popen) -> None:
    with suppress(subprocess.TimeoutExpired):
        process.wait(timeout=REAP_SECONDS)
