"""GGUF files in a folder tree, as LM Studio, Jan, GPT4All or a person keep them.

The walk is bounded, because a folder a person adds may be a whole drive: it
goes `depth` folders down, never into a hidden folder or through a linked one,
and lists at most `_MOST_ENTRIES` entries in all, keeping the files it read
before the budget ran out. A split build is one candidate for all of its parts,
offered from its first.
"""

import logging
import os
import re
from itertools import islice
from pathlib import Path

from modules.llm.catalog.local.engines.llamacpp.elsewhere.candidate import Candidate
from modules.llm.catalog.local.engines.llamacpp.elsewhere.places import App

logger = logging.getLogger(__name__)

_MOST_ENTRIES = 20_000
_PART = re.compile(r"^(?P<stem>.+)-(?P<part>\d{5})-of-(?P<total>\d{5})\.gguf$", re.I)


def in_tree(root: Path, app: App, *, depth: int) -> list[Candidate]:
    found: list[Candidate] = []
    budget = [_MOST_ENTRIES]
    _walk(root, root, app, depth, found, budget)
    if budget[0] <= 0:
        logger.info("stopped reading %s after %d entries", app.value, _MOST_ENTRIES)
    return found


def _walk(
    root: Path,
    folder: Path,
    app: App,
    depth: int,
    found: list[Candidate],
    budget: list[int],
) -> None:
    try:
        with os.scandir(folder) as listing:
            # No more than the budget leaves, before anything is held or sorted:
            # a folder a person adds may be a whole drive. One past it is read,
            # so running out is noticed.
            entries = sorted(
                islice(listing, max(budget[0], 0) + 1), key=lambda e: e.name
            )
    except OSError:
        return
    files = []
    for entry in entries:
        budget[0] -= 1
        if budget[0] < 0:
            break  # what was read is kept, below
        if entry.name.startswith("."):
            continue
        try:
            if entry.is_dir(follow_symlinks=False):
                if depth > 0:
                    _walk(root, Path(entry.path), app, depth - 1, found, budget)
            elif entry.name.lower().endswith(".gguf") and entry.is_file():
                files.append(entry.name)
        except OSError:
            continue
    names = set(files)
    for name in files:
        candidate = _candidate(root, folder, name, names, app)
        if candidate is not None:
            found.append(candidate)


def _candidate(
    root: Path, folder: Path, name: str, names: set[str], app: App
) -> Candidate | None:
    path = folder / name
    parts: tuple[Path, ...] = (path,)
    missing = False
    if match := _PART.match(name):
        if int(match["part"]) != 1:
            return None  # offered from its first part
        total = int(match["total"])
        expected = [
            f"{match['stem']}-{n:05d}-of-{match['total']}.gguf"
            for n in range(1, total + 1)
        ]
        present = {n.lower(): n for n in names}
        missing = any(e.lower() not in present for e in expected)
        parts = tuple(
            folder / present[e.lower()] for e in expected if e.lower() in present
        )
    relative = folder.relative_to(root).as_posix()
    return Candidate(
        app,
        path,
        parts,
        source=relative if relative != "." else None,
        group=folder,
        missing_parts=missing,
    )
