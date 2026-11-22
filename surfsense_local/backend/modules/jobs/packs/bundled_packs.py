"""SurfSense's own job packs, shipped inside the app and installed when the API starts (ADR
0092). A version already installed, or a newer one, stays as it is, so starting costs nothing
once a pack is in place and an imported newer pack is never replaced by an older one.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from modules.jobs.packs.delivery.acceptance import accept_imported
from modules.jobs.packs.dev_packs import install_at_start
from modules.jobs.packs.installed import installed_packs
from modules.jobs.packs.manifest import (
    PackRefusedError,
    parse_manifest,
    read_raw_manifest,
    version_key,
)
from modules.jobs.runs.in_flight import pack_in_use

# Read by path: the frozen build carries this folder as data (bundling/api_inputs.py).
BUNDLED_PACKS = Path(__file__).with_name("bundled")


def bundled_packs() -> list[Path]:
    if not BUNDLED_PACKS.is_dir():
        return []
    return sorted(
        folder
        for folder in BUNDLED_PACKS.iterdir()
        if folder.is_dir() and not folder.name.startswith(".")
    )


def install_bundled_packs(sessions: sessionmaker[Session]) -> None:
    installed = {
        pack.manifest.id: version_key(pack.manifest.version)
        for pack in installed_packs()
    }

    def in_use(pack_id: str) -> bool:
        with sessions() as session:
            return pack_in_use(session, pack_id)

    install_at_start(
        (folder for folder in bundled_packs() if not _held(folder, installed)),
        # A run under way keeps its version; the next start installs the new one.
        accept=accept_imported(in_use),
    )


def _held(folder: Path, installed: dict[str, tuple[int, int, int]]) -> bool:
    """Whether this version, or a newer one, is installed already; a folder that cannot be
    read is left to the install, which logs why."""
    try:
        manifest = parse_manifest(read_raw_manifest(folder))
    except (PackRefusedError, OSError):
        return False
    held = installed.get(manifest.id)
    return held is not None and held >= version_key(manifest.version)
