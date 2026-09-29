"""Where an upload's bytes live: alone in documents/<id>/, under its own name."""

from pathlib import Path

from pathvalidate import sanitize_filename

from modules.documents.models import Document
from shared.config import get_storage_settings

# Windows caps a whole path at 260 characters unless LongPathsEnabled is set,
# and the data folder's prefix takes about 70 of them.
MAX_NAME_BYTES = 120

# Written beside every original before this layout and left there. Never an
# original, so a folder whose original was deleted reads as missing.
LEGACY_EXTRACTED = "extracted.md"


def stored_name(filename: str, suffix: str) -> str:
    """The file name an upload is stored under, ending in its validated suffix."""
    name = Path(filename).name
    stem = name[: -len(suffix)] if suffix and name.lower().endswith(suffix) else name
    # Universal, not this OS: a data folder can be copied to another machine.
    # A leading dot would hide the file from the search for the original.
    stem = sanitize_filename(
        stem.lstrip("."),
        platform="universal",
        max_len=MAX_NAME_BYTES - len(suffix.encode()),
    )
    stored = (stem or "untitled") + suffix
    if stored.casefold() == LEGACY_EXTRACTED:
        return f"{stem} (1){suffix}"
    return stored


def original_path(document: Document) -> Path | None:
    """The upload's file, or None when it is no longer on disk.

    Reads both layouts: a folder's one file, or a legacy original.<ext> beside
    extracted.md. No name is stored, so the folder is the only record.
    """
    directory = get_storage_settings().document_dir(document.workspace_id, document.id)
    try:
        entries = list(directory.iterdir())
    except FileNotFoundError:
        return None
    files = [
        entry
        for entry in entries
        if entry.is_file()
        and not _left_by_the_os(entry.name)
        and entry.name.casefold() != LEGACY_EXTRACTED
    ]
    return files[0] if len(files) == 1 else None


def _left_by_the_os(name: str) -> bool:
    # Finder writes .DS_Store into any folder it shows; Explorer writes the other two.
    return name.startswith(".") or name.casefold() in {"thumbs.db", "desktop.ini"}
