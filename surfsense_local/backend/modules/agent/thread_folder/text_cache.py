"""One file per version of a source's text, hard-linked into every thread that uses it.

Defender scans a file the first time it is read after being written (~8 ms
each), so a copy per thread would pay that in every thread; a link to one
cached file pays it once per version per machine. Cache files stay writable:
on Windows a read-only link cannot be unlinked, and clearing the flag clears
it on every link. The edit deny and `bash: deny` keep the agent off them.
"""

import contextlib
import hashlib
import logging
import os
import time
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

# Old enough that no sync still means to link it; a link made since keeps it.
UNLINKED_SECONDS = 10 * 60

_told_copying: set[Path] = set()


def cached_text(text_dir: Path, document_id: int, data: bytes) -> Path:
    """The cache file holding this text, written if new; other versions of it are dropped.

    A version another thread still links stays readable there, and the sweep
    collects it once nothing does.
    """
    key = hashlib.sha256(data).hexdigest()[:16]
    cached = text_dir / f"{document_id}-{key}.md"
    if cached.is_file():
        return cached
    text_dir.mkdir(parents=True, exist_ok=True)
    _write_whole(cached, data)
    for older in text_dir.glob(f"{document_id}-*.md"):
        if older.name != cached.name:
            with contextlib.suppress(PermissionError, FileNotFoundError):
                older.unlink()
    return cached


def link_view(cached: Path, view: Path, data: bytes) -> None:
    """Make `view` the cached file itself; a copy where the disk cannot hard-link (FAT, exFAT)."""
    try:
        if os.path.samefile(cached, view):
            return
    except FileNotFoundError:
        pass
    view.parent.mkdir(parents=True, exist_ok=True)
    # os.link never overwrites: link beside the view, then replace it in one step.
    # No longer than the view's name, so it fits wherever the layout put the view;
    # unique, since the name ends in the source's id and the thread's lock is held.
    temp = view.with_name(f".{view.name[1:]}")
    temp.unlink(missing_ok=True)
    try:
        try:
            os.link(cached, temp)
        except FileNotFoundError:
            # Another thread's sync dropped this version as it changed again.
            _write_whole(cached, data)
            os.link(cached, temp)
    except OSError:
        if _holds(view, data):
            return
        _say_copying(cached.parent)
        temp.write_bytes(data)
    os.replace(temp, view)


def sweep_unlinked(text_dir: Path) -> None:
    """Delete cache files no thread links: deleted sources, old versions, a race's leftovers.

    Read by link count alone, so no content is read.
    """
    if not text_dir.is_dir():
        return
    now = time.time()
    for entry in os.scandir(text_dir):
        # DirEntry.stat reports no link count on Windows.
        try:
            stat = os.lstat(entry.path)
        except FileNotFoundError:
            continue
        if stat.st_nlink == 1 and now - stat.st_mtime > UNLINKED_SECONDS:
            with contextlib.suppress(
                PermissionError, FileNotFoundError, IsADirectoryError
            ):
                os.unlink(entry.path)


def _say_copying(text_dir: Path) -> None:
    if text_dir not in _told_copying:
        _told_copying.add(text_dir)
        logger.warning(
            "%s cannot hold hard links; each thread gets its own copy of a source",
            text_dir,
        )


def _holds(path: Path, data: bytes) -> bool:
    """Whether the file already has exactly this text; the size answers most cases unread."""
    try:
        return path.stat().st_size == len(data) and path.read_bytes() == data
    except FileNotFoundError:
        return False


def _write_whole(path: Path, data: bytes) -> None:
    """Replace the file in one step, so a reader never sees half.

    The partial name is shorter than a cache file's, so it fits wherever that does.
    """
    partial = path.with_name(f".{uuid.uuid4().hex[:8]}.tmp")
    partial.write_bytes(data)
    os.replace(partial, path)
