"""Bring a thread's `sources/` in line with the sources its turn may use.

Reads come in short transactions and every file is written after they commit:
SQLite's write lock is taken at BEGIN, and the first read of a freshly written
file waits on the virus scanner.
"""

import contextlib
import json
import os
import threading
import time
from collections.abc import Sequence
from pathlib import Path, PurePosixPath

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from modules.agent.thread_folder.instruction_names import rename_instruction_files
from modules.agent.thread_folder.layout import (
    FIGURES,
    OUTPUTS,
    PAGES,
    SOURCES,
    ensure_thread_folder,
    remove_entry,
    thread_lock,
)
from modules.agent.thread_folder.retire_workspace_folder import retire_once
from modules.agent.thread_folder.scope_paths import scope_paths
from modules.agent.thread_folder.text_cache import (
    cached_text,
    link_view,
    sweep_unlinked,
)
from modules.chat.models import ChatThread
from modules.documents.source_figures import parse_figure_name
from shared.config import get_storage_settings

# Texts read per transaction: about 8 MB at 40 KB a source.
PAGE_SIZE = 200
# The cache sweep reads every cache file's link count; once in a while is enough.
SWEEP_SECONDS = 10 * 60


class ThreadGoneError(LookupError):
    """The thread was deleted before its folder could be synced."""


_sweep_guard = threading.Lock()
_swept: dict[Path, float] = {}


def sync_thread_folder(
    session: Session, thread: ChatThread, document_ids: Sequence[int]
) -> Path:
    """Mirror the sources `document_ids` names that have text; returns the thread's folder.

    Commits as it goes, so the caller must hold no transaction it means to keep.
    """
    workspace_id, thread_id = thread.workspace_id, thread.id
    storage = get_storage_settings()
    text_dir = storage.agent_text_dir(workspace_id)
    # A transaction holds the write lock from its BEGIN. Waiting for the thread's
    # lock with one open would stop the sync that holds it at its next read.
    session.commit()
    with thread_lock(storage.thread_working_dir(workspace_id, thread_id)):
        # Checked under the lock a deletion takes, so a deleted thread's folder stays gone.
        _require_same_thread(session, thread)
        folder = ensure_thread_folder(workspace_id, thread_id)
        sources = folder / SOURCES
        retire_once(session, workspace_id)
        paths, with_text = _layout(session, workspace_id, document_ids, sources)
        mirrored = [i for i in with_text if i in paths]
        for start in range(0, len(mirrored), PAGE_SIZE):
            texts = _texts(session, mirrored[start : start + PAGE_SIZE])
            session.commit()
            for document_id, content in texts:
                data = content.encode("utf-8")
                cached = cached_text(text_dir, document_id, data)
                link_view(cached, sources / paths[document_id], data)
        _clean(sources, [paths[i] for i in mirrored], set(document_ids))
        rename_instruction_files(folder / OUTPUTS)
        _sweep_now_and_then(text_dir)
    return folder


def _require_same_thread(session: Session, thread: ChatThread) -> None:
    """The thread still exists with its session: a deleted newest id is given out again."""
    session_id = session.scalar(
        select(ChatThread.opencode_session_id).where(ChatThread.id == thread.id)
    )
    session.commit()
    if session_id is None or session_id != thread.opencode_session_id:
        raise ThreadGoneError(f"thread {thread.id} is no longer the agent's")


def _layout(
    session: Session, workspace_id: int, document_ids: Sequence[int], sources: Path
) -> tuple[dict[int, PurePosixPath], list[int]]:
    """Every path, and which sources have text to mirror, in one short transaction."""
    paths = scope_paths(session, workspace_id, document_ids, sources)
    with_text = list(
        session.scalars(
            text(
                "SELECT id FROM documents WHERE workspace_id = :ws "
                "AND content IS NOT NULL "
                "AND id IN (SELECT value FROM json_each(:ids)) ORDER BY id"
            ),
            {"ws": workspace_id, "ids": json.dumps(list(document_ids))},
        )
    )
    session.commit()
    return paths, with_text


def _texts(session: Session, ids: list[int]) -> list[tuple[int, str]]:
    return [
        (row.id, row.content)
        for row in session.execute(
            text(
                "SELECT id, content FROM documents WHERE content IS NOT NULL "
                "AND id IN (SELECT value FROM json_each(:ids))"
            ),
            {"ids": json.dumps(ids)},
        )
    ]


def _clean(sources: Path, wanted: list[PurePosixPath], in_scope: set[int]) -> None:
    """Remove what the scope no longer holds, and anything planted; prune empty folders.

    Compared case-insensitively, since a title that changed only in case keeps
    its old name on Windows and macOS.
    """
    by_fold = {path.as_posix().casefold(): path for path in wanted}
    _prune(sources, sources, by_fold)
    _drop_others(sources / FIGURES, in_scope, _figure_source)
    _drop_others(sources / PAGES, in_scope, _page_source)


def _prune(sources: Path, directory: Path, wanted: dict[str, PurePosixPath]) -> None:
    for entry in list(os.scandir(directory)):
        path = Path(entry.path)
        if entry.is_symlink() or entry.is_junction():
            remove_entry(path)
        elif entry.is_dir():
            if directory == sources and entry.name in (FIGURES, PAGES):
                continue
            _prune(sources, path, wanted)
            with contextlib.suppress(OSError):  # not empty
                path.rmdir()
        else:
            relative = path.relative_to(sources).as_posix()
            exact = wanted.get(relative.casefold())
            if exact is None or (
                exact.as_posix() != relative and not _same(path, sources / exact)
            ):
                remove_entry(path)


def _drop_others(directory: Path, in_scope: set[int], source_of) -> None:
    """A shown figure or drawn page leaves with its source's tick; anything else there goes."""
    if not directory.is_dir():
        return
    for entry in directory.iterdir():
        owner = source_of(entry.name) if entry.is_file() else None
        if owner is None or owner not in in_scope:
            remove_entry(entry)


def _figure_source(name: str) -> int | None:
    if not name.endswith(".png"):
        return None
    parsed = parse_figure_name(name.removesuffix(".png"))
    return parsed[0] if parsed is not None else None


def _page_source(name: str) -> int | None:
    stem, dash, page = name.removesuffix(".png").rpartition("-p")
    if not (name.endswith(".png") and dash and stem.isdigit() and page.isdigit()):
        return None
    return int(stem)


def _same(a: Path, b: Path) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def _sweep_now_and_then(text_dir: Path) -> None:
    now = time.monotonic()
    with _sweep_guard:
        last = _swept.get(text_dir)
        if last is not None and now - last < SWEEP_SECONDS:
            return
        _swept[text_dir] = now
    sweep_unlinked(text_dir)
