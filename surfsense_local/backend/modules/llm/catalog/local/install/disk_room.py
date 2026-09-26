"""Refuse a download the disk cannot hold, before any byte moves."""

from pathlib import Path
from shutil import disk_usage

from modules.llm.catalog.local.install.plan import InstallRefusedError

# Left free once it lands: a full disk takes the database and the logs with it.
HEADROOM = 1 << 30


def refuse_without_room(folder: Path, needed: int) -> None:
    """`needed` is what the download fetches, not what is already there."""
    existing = next(p for p in (folder, *folder.parents) if p.exists())
    free = disk_usage(existing).free
    if free < needed + HEADROOM:
        raise InstallRefusedError(
            f"This download needs {_gb(needed + HEADROOM)} free; "
            f"this computer has {_gb(free)}."
        )


def _gb(size: int) -> str:
    return f"{size / 1e9:.1f} GB"
