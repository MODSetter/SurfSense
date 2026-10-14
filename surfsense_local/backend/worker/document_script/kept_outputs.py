"""What an analysis saved in its output folder, moved where the user and later document scripts find it."""

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

# Enough for a handful of tables and charts; more is a script saving in a loop.
MAX_FILES = 20
MAX_FILE_BYTES = 25 * 1024 * 1024
# A kept file's stem: what a document script's image name may hold, short
# enough for the thread folder's Windows path budget.
KEPT_STEM = re.compile(r"[A-Za-z0-9_-]{1,40}")
# Tables, charts and data files. Never Markdown: a file named like AGENTS.md
# in a thread's outputs would read to opencode as instructions.
KEPT_SUFFIXES = frozenset(
    {".csv", ".tsv", ".png", ".jpg", ".jpeg", ".svg", ".xlsx", ".json", ".txt"}
)
_UNSAFE = re.compile(r"[^A-Za-z0-9_-]+")


@dataclass(frozen=True)
class KeptOutputs:
    kept: tuple[str, ...]
    left_out: tuple[str, ...]


def keep_outputs(output_dir: Path, keep_in: Path) -> KeptOutputs:
    """Move the files at output_dir's top into keep_in under safe names, in name order.

    A folder, a file of another kind, one past MAX_FILE_BYTES or past MAX_FILES
    is left out by its own name.
    """
    kept: list[str] = []
    left_out: list[str] = []
    taken: set[str] = set()
    for entry in sorted(output_dir.iterdir(), key=lambda path: path.name):
        if (
            not entry.is_file()
            or entry.is_symlink()
            or entry.suffix.lower() not in KEPT_SUFFIXES
            or len(kept) >= MAX_FILES
            or entry.stat().st_size > MAX_FILE_BYTES
        ):
            left_out.append(entry.name)
            continue
        name = _safe_name(entry.name, taken)
        keep_in.mkdir(parents=True, exist_ok=True)
        shutil.move(entry, keep_in / name)
        kept.append(name)
    return KeptOutputs(tuple(kept), tuple(left_out))


def _safe_name(name: str, taken: set[str]) -> str:
    """Letters, digits, `_` and `-`, cut to fit, its suffix kept in lower case; unique ignoring case."""
    path = Path(name)
    suffix = path.suffix.lower()
    stem = name[: -len(suffix)].strip()
    stem = _UNSAFE.sub("_", stem).strip("_")[:40] or "output"
    candidate, n = stem, 1
    while f"{candidate}{suffix}".casefold() in taken:
        n += 1
        candidate = f"{stem[: 40 - len(str(n)) - 1]}-{n}"
    taken.add(f"{candidate}{suffix}".casefold())
    return f"{candidate}{suffix}"
