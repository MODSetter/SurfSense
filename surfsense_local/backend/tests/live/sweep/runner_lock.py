"""One runner per sweep folder: a second would record the first's live cases as interrupted and pay for them again.

The lock is the OS's on runner.lock, so it ends with the process that held it,
however that process ends.
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

LOCK = "runner.lock"
# Windows locks a byte range against reads too, so the holder's pid sits before it.
_PID_BYTES = 16
_LOCKED_BYTE = 64


class SweepBusyError(RuntimeError):
    """Another runner holds this sweep folder."""


@contextmanager
def held(out: Path) -> Iterator[None]:
    """Hold the folder's lock for the block; SweepBusyError, naming the holder, if another runner has it."""
    out.mkdir(parents=True, exist_ok=True)
    path = out / LOCK
    fd = os.open(path, os.O_RDWR | os.O_CREAT)
    try:
        if not _lock(fd):
            raise SweepBusyError(
                f"a sweep is already running in {out} (pid {_holder(fd)}); "
                "`report` shows its progress"
            )
        os.lseek(fd, 0, os.SEEK_SET)
        os.write(fd, str(os.getpid()).ljust(_PID_BYTES).encode())
        try:
            yield
        finally:
            _unlock(fd)
    finally:
        os.close(fd)


def _lock(fd: int) -> bool:
    try:
        if os.name == "nt":
            import msvcrt

            os.lseek(fd, _LOCKED_BYTE, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def _unlock(fd: int) -> None:
    if os.name == "nt":
        import msvcrt

        os.lseek(fd, _LOCKED_BYTE, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_UN)


def _holder(fd: int) -> str:
    os.lseek(fd, 0, os.SEEK_SET)
    return os.read(fd, _PID_BYTES).decode(errors="replace").strip() or "unknown"
