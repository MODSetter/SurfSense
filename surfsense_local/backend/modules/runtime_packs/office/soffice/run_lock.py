"""One LibreOffice run at a time, across the API and every worker process.

An OS lock on a file, not a lock in memory: the engines, Studio and ingest
workers are separate processes. The OS drops it when its holder dies.
"""

import os
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from modules.runtime_packs.office.soffice.errors import OfficeBusy

_POLL_SECONDS = 0.1


@contextmanager
def run_lock(path: Path, *, wait_until: float) -> Iterator[None]:
    """Hold the lock, waiting until the monotonic `wait_until` and then raising OfficeBusy."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        while not _try_lock(fd):
            if time.monotonic() >= wait_until:
                raise OfficeBusy("LibreOffice was busy with another file")
            time.sleep(_POLL_SECONDS)
        try:
            yield
        finally:
            _unlock(fd)
    finally:
        os.close(fd)


if sys.platform == "win32":
    import msvcrt

    def _try_lock(fd: int) -> bool:
        os.lseek(fd, 0, os.SEEK_SET)
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except OSError:
            return False
        return True

    def _unlock(fd: int) -> None:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _try_lock(fd: int) -> bool:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        return True

    def _unlock(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_UN)
