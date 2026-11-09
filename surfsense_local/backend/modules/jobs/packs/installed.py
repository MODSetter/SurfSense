"""The packs installed on this computer, the newest version of each, re-checked against its
signature and its manifest when read."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from modules.jobs.packs.install_lock import INSTALLING
from modules.jobs.packs.integrity import check_files
from modules.jobs.packs.manifest import (
    PackJob,
    PackManifest,
    PackRefusedError,
    parse_manifest,
    read_raw_manifest,
    version_key,
)
from modules.jobs.packs.signature import check_signature
from shared.config import get_storage_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InstalledPack:
    manifest: PackManifest
    folder: Path

    def job(self, key: str) -> PackJob | None:
        return next((job for job in self.manifest.jobs if job.key == key), None)

    def path(self, relative: str) -> Path:
        return self.folder / relative


def packs_dir() -> Path:
    return get_storage_settings().data_dir / "job-packs"


def installed_packs(root: Path | None = None) -> list[InstalledPack]:
    """The newest version of each pack still signed and matching its manifest, by id; a version
    that fails its checks is left out and logged."""
    root = root or packs_dir()
    if not root.is_dir():
        return []
    newest: dict[str, InstalledPack] = {}
    # A name starting with a dot is an install's, a download's or an import's scratch.
    for folder in sorted(p for p in root.iterdir() if not p.name.startswith(".")):
        for pack in _verified_versions(folder):
            kept = newest.get(pack.manifest.id)
            if kept is None or version_key(pack.manifest.version) > version_key(
                kept.manifest.version
            ):
                newest[pack.manifest.id] = pack
    return [newest[pack_id] for pack_id in sorted(newest)]


def find_job(
    key: str, root: Path | None = None
) -> tuple[InstalledPack, PackJob] | None:
    """The job from the highest version of any pack holding it, as the licence server picks a
    pack: one id per job is the publisher's rule, and a second id imported by hand is not."""
    holding = [
        (pack, job)
        for pack in installed_packs(root)
        if (job := pack.job(key)) is not None
    ]
    if not holding:
        return None
    return max(
        holding,
        key=lambda found: (
            version_key(found[0].manifest.version),
            found[0].manifest.id,
        ),
    )


def _verified_versions(folder: Path) -> list[InstalledPack]:
    """Every version of one pack that passes its checks. A version moved away while it was read
    gave way to another, put in place first; installs in a row can each move the one a read
    found, so the folder is read once more with no install under way."""
    found, vanished = _read_versions(folder)
    if not vanished:
        return found
    with INSTALLING:
        found, _ = _read_versions(folder)
    return found


def _read_versions(folder: Path) -> tuple[list[InstalledPack], bool]:
    """The versions that pass their checks, and whether one went while it was read."""
    try:
        versions = sorted(p for p in folder.iterdir() if p.is_dir())
    except OSError:
        return [], False
    found: list[InstalledPack] = []
    vanished = False
    for version in versions:
        try:
            raw = read_raw_manifest(version)
            manifest = parse_manifest(raw)
            check_signature(version, raw)
            check_files(version, manifest)
        except (PackRefusedError, OSError) as refused:
            if not version.is_dir():
                vanished = True
                continue
            logger.warning("job pack %s left out: %s", version, _reason(refused))
            continue
        found.append(InstalledPack(manifest, version))
    return found, vanished


def _reason(refused: Exception) -> str:
    return refused.message if isinstance(refused, PackRefusedError) else str(refused)
