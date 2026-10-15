"""The names inside a thread's folder, making it, and the lock its syncs take."""

import os
import shutil
import threading
from pathlib import Path

from shared.config import get_storage_settings

SOURCES = "sources"
FIGURES = "figures"
PAGES = "pages"
OUTPUTS = "outputs"
PREVIEWS = "previews"

_locks_guard = threading.Lock()
_locks: dict[Path, threading.Lock] = {}


def ensure_thread_folder(workspace_id: int, thread_id: int) -> Path:
    """The thread's folder, with `sources/` and `outputs/` in it."""
    folder = get_storage_settings().thread_working_dir(workspace_id, thread_id)
    (folder / SOURCES).mkdir(parents=True, exist_ok=True)
    (folder / OUTPUTS).mkdir(exist_ok=True)
    return folder


def fresh_thread_folder(workspace_id: int, thread_id: int) -> Path:
    """A new thread's folder, without what a deleted thread of the same id left.

    SQLite gives a deleted newest row's id to the next one. Raises OSError
    when what was left cannot be removed.
    """
    folder = get_storage_settings().thread_working_dir(workspace_id, thread_id)
    if folder.exists() or folder.is_symlink() or folder.is_junction():
        remove_entry(folder)
        if folder.exists():
            raise OSError(f"{folder} still holds a deleted thread's files")
    return ensure_thread_folder(workspace_id, thread_id)


def thread_lock(folder: Path) -> threading.Lock:
    """One per thread folder, so two syncs of one thread never interleave."""
    with _locks_guard:
        return _locks.setdefault(folder, threading.Lock())


def forget_thread_lock(folder: Path) -> None:
    """Drop a deleted thread's lock, so the table does not grow with every thread ever made."""
    with _locks_guard:
        _locks.pop(folder, None)


def remove_thread_folder(folder: Path) -> None:
    """Delete a deleted thread's folder once any sync of it has finished.

    A sync that starts later finds the thread gone and makes nothing.
    """
    with thread_lock(folder):
        shutil.rmtree(folder, ignore_errors=True)
    forget_thread_lock(folder)


def remove_entry(entry: Path) -> None:
    """Delete a file or a folder; a link or junction is unlinked, never followed."""
    if entry.is_symlink() or entry.is_junction():
        try:
            os.unlink(entry)
        except OSError:
            os.rmdir(entry)  # a directory link on Windows
    elif entry.is_dir():
        shutil.rmtree(entry, ignore_errors=True)
    else:
        entry.unlink(missing_ok=True)
