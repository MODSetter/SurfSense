"""Where each source's text sits in a thread's `sources/`: the user's folders, made safe.

Every decision reads the workspace's live folders and the source's own row,
never the scope, so ticking or unticking a source never moves another's path.
"""

import logging
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import PurePosixPath

from modules.agent.thread_folder.layout import FIGURES, OUTPUTS, PAGES
from modules.agent.thread_folder.path_budget import (
    LONGEST_DIRECTORY,
    LONGEST_PATH,
    cut,
    units,
)

logger = logging.getLogger(__name__)

# Characters some file system refuses, and the separators that would make a name a path.
_UNSAFE = re.compile(r'[\x00-\x1f<>:"/\\|?*]')
# Short enough that a suffix and the extension still fit Windows' 255-character names.
_LONGEST_SEGMENT = 100
# A folder must leave this much for a file in it, or it is cut shorter.
_ROOM_FOR_A_FILE = 24
_CUT_TO = 8

_DEVICES = frozenset(
    {"con", "prn", "aux", "nul", "conin$", "conout$"}
    | {f"{port}{n}" for port in ("com", "lpt") for n in "0123456789¹²³"}
)
# opencode reads these as instructions wherever it walks (CLAUDE.md only once enabled).
INSTRUCTION_NAMES = frozenset({"agents.md", "claude.md", "context.md"})
# The edit rules allow a path holding `/outputs/`; on macOS they match case as
# written, so `Sources/…/outputs/` would miss the `sources/` deny.
_RESERVED = INSTRUCTION_NAMES | {OUTPUTS}
_SURFSENSE_TOP = frozenset({FIGURES, PAGES})
# Endings a folder could use to pass for a suffixed folder or a source's file.
_SUFFIXED = re.compile(r" \[f\d+\]$| \[\d+\]\.md$", re.IGNORECASE)


@dataclass(frozen=True)
class MirroredSource:
    """A source's own row: its id, its title and the folder it is filed in."""

    id: int
    title: str
    folder_id: int | None


@dataclass(frozen=True)
class LiveFolder:
    """A folder that is neither trashed nor being deleted."""

    id: int
    parent_id: int | None
    name: str


def file_name(title: str, document_id: int) -> str:
    """A source's file: its title, made safe, and its id, which citations and tools read."""
    return f"{_safe(title)} [{document_id}].md"


def lay_out(
    base: str, docs: Iterable[MirroredSource], folders: Iterable[LiveFolder]
) -> dict[int, PurePosixPath]:
    """Each source's path relative to `sources/`, whose absolute path is `base`.

    A source too long to place even at the top is left out, with a warning.
    """
    directories: dict[int | None, PurePosixPath] = {
        None: PurePosixPath(),
        **_directories(units(base), list(folders)),
    }
    paths: dict[int, PurePosixPath] = {}
    for doc in docs:
        path = _placed(units(base), doc, directories.get(doc.folder_id))
        if path is None:
            logger.warning("source %s has no path short enough to mirror", doc.id)
            continue
        assert all(
            part not in ("", ".", "..") and "/" not in part and "\\" not in part
            for part in path.parts
        ), path
        paths[doc.id] = path
    return paths


def _placed(
    base: int, doc: MirroredSource, directory: PurePosixPath | None
) -> PurePosixPath | None:
    """In its folder (the top for an unfiled one), its title cut to fit if need be; else flat, else nowhere."""
    title = _safe(doc.title)
    ending = f" [{doc.id}].md"
    if directory is not None:
        room = LONGEST_PATH - _length(base, directory) - 1 - len(ending)
        kept = cut(title, room).rstrip(" .") if room > 0 else ""
        if kept:
            return directory / f"{kept}{ending}"
    flat = f"{title[:_CUT_TO].rstrip(' .')}{ending}"
    if base + 1 + units(flat) <= LONGEST_PATH:
        return PurePosixPath(flat)
    return None


def _directories(base: int, folders: list[LiveFolder]) -> dict[int, PurePosixPath]:
    """Each live folder's one directory, cut from the deepest segment up until it fits.

    A folder that cannot fit has none, and its sources go flat.
    """
    by_id = {folder.id: folder for folder in folders}
    names = _sibling_names(folders)
    cut: set[int] = set()

    def chain(folder: LiveFolder) -> list[int]:
        ids: list[int] = []
        seen: set[int] = set()
        while folder is not None and folder.id not in seen:
            seen.add(folder.id)
            ids.append(folder.id)
            folder = by_id.get(folder.parent_id)
        return ids[::-1]

    def directory(ids: list[int]) -> PurePosixPath:
        return PurePosixPath(*(names[i] for i in ids))

    def too_long(ids: list[int]) -> bool:
        length = _length(base, directory(ids))
        return (
            length > LONGEST_DIRECTORY or LONGEST_PATH - length - 1 < _ROOM_FOR_A_FILE
        )

    chains = sorted(
        (chain(folder) for folder in folders), key=lambda ids: (len(ids), ids)
    )
    for ids in chains:
        if by_id[ids[0]].parent_id is not None:
            continue  # a folder whose root is not live is no directory
        while too_long(ids):
            uncut = [i for i in ids if i not in cut]
            if not uncut:
                break
            deepest = uncut[-1]
            cut.add(deepest)
            shorter = f"{names[deepest][:_CUT_TO].rstrip(' .')} [f{deepest}]"
            if units(shorter) < units(names[deepest]):
                names[deepest] = shorter
    return {
        ids[-1]: directory(ids)
        for ids in chains
        if by_id[ids[0]].parent_id is None and not too_long(ids)
    }


def _sibling_names(folders: list[LiveFolder]) -> dict[int, str]:
    """Each folder's safe name, with its id where siblings would share one."""
    names = {
        folder.id: _safe(folder.name, top=folder.parent_id is None)
        for folder in folders
    }
    keys: dict[tuple[int | None, str], list[int]] = {}
    for folder in folders:
        key = unicodedata.normalize("NFC", names[folder.id]).casefold()
        keys.setdefault((folder.parent_id, key), []).append(folder.id)
    for (_, key), ids in keys.items():
        if len(ids) > 1 or _SUFFIXED.search(key):
            for folder_id in ids:
                names[folder_id] = f"{names[folder_id]} [f{folder_id}]"
    return names


def _safe(name: str, *, top: bool = False) -> str:
    """A name any file system takes, that neither Windows nor opencode reads specially.

    A leading dot would hide it from grep and glob, which skip hidden entries.
    """
    safe = _UNSAFE.sub("_", name).strip(" .")[:_LONGEST_SEGMENT].rstrip(" .")
    if not safe:
        return "untitled"
    stem = safe.split(".", 1)[0].rstrip()
    if stem.casefold() in _DEVICES:
        return f"{stem}_{safe[len(stem) :]}"
    folded = safe.casefold()
    if folded in _RESERVED or (top and folded in _SURFSENSE_TOP):
        return f"{safe}_"
    return safe


def _length(base: int, directory: PurePosixPath) -> int:
    return base + sum(1 + units(part) for part in directory.parts)
