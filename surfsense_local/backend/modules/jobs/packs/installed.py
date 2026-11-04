"""The packs installed on this computer, each re-checked against its signature and its
manifest when read."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from modules.jobs.packs.integrity import check_files
from modules.jobs.packs.manifest import (
    PackJob,
    PackManifest,
    PackRefusedError,
    parse_manifest,
    read_raw_manifest,
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
    """Every pack still signed and matching its manifest; any other is left out and logged."""
    found: list[InstalledPack] = []
    root = root or packs_dir()
    if not root.is_dir():
        return found
    for folder in sorted(p for p in root.glob("*/*") if p.is_dir()):
        if folder.parent.name.startswith("."):
            continue
        try:
            raw = read_raw_manifest(folder)
            manifest = parse_manifest(raw)
            check_signature(folder, raw)
            check_files(folder, manifest)
        except PackRefusedError as refused:
            logger.warning("job pack %s left out: %s", folder, refused.message)
            continue
        found.append(InstalledPack(manifest, folder))
    return found


def find_job(
    key: str, root: Path | None = None
) -> tuple[InstalledPack, PackJob] | None:
    for pack in installed_packs(root):
        job = pack.job(key)
        if job is not None:
            return pack, job
    return None
