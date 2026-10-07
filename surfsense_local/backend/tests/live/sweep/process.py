"""One case's pytest process: started, its whole tree's memory sampled every second, killed at the case's time limit."""

import os
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import psutil

_SAMPLE_SECONDS = 1.0


@dataclass(frozen=True)
class Process:
    """How the case's process ended."""

    exit_code: int | None
    seconds: float
    timed_out: bool = False
    peak_mb: int | None = None
    lane: int | None = None


def kill_tree(pid: int) -> None:
    """The case and everything it started: opencode, LibreOffice, script runners."""
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/pid", str(pid), "/t", "/f"], check=False, capture_output=True
        )
        return
    try:
        parent = psutil.Process(pid)
        for child in parent.children(recursive=True):
            child.kill()
        parent.kill()
    except psutil.NoSuchProcess:
        pass


def tree_working_set(pid: int) -> int:
    """Bytes the process tree holds in RAM now."""
    try:
        root = psutil.Process(pid)
        tree = [root, *root.children(recursive=True)]
    except psutil.NoSuchProcess:
        return 0
    total = 0
    for process in tree:
        try:
            total += process.memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return total


def run_case(
    command: list[str],
    *,
    env: dict[str, str],
    cwd: Path,
    log: Path,
    time_limit: float,
    lane: int,
    kill: threading.Event,
    on_sample: Callable[[int], None] = lambda _: None,
) -> Process:
    """Run to the end, to the time limit, or until `kill` is set; pytest's output goes to `log`."""
    started = time.monotonic()
    peak = 0
    timed_out = False
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("wb") as output:
        child = subprocess.Popen(
            command, cwd=cwd, env=env, stdout=output, stderr=subprocess.STDOUT
        )
        while child.poll() is None:
            now = tree_working_set(child.pid)
            peak = max(peak, now)
            on_sample(now)
            if time.monotonic() - started > time_limit:
                timed_out = True
                kill_tree(child.pid)
                break
            if kill.wait(_SAMPLE_SECONDS):
                kill_tree(child.pid)
                break
        exit_code = child.wait()
    return Process(
        exit_code=exit_code,
        seconds=time.monotonic() - started,
        timed_out=timed_out,
        peak_mb=peak >> 20,
        lane=lane,
    )
