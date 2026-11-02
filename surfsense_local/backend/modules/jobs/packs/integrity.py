"""A pack holds exactly the files its manifest lists, each with the sha256 listed.

The manifest's own signature is checked once packs are signed; until then the
sha256s hold a pack together but do not say who made it.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from modules.jobs.packs.manifest import MANIFEST, PackManifest, PackRefusedError

# Room for prompts, mappings and a skill; a pack this large is not one.
MAX_PACK_BYTES = 50 * 1024 * 1024


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def check_files(folder: Path, manifest: PackManifest) -> None:
    """Refuse a pack with a file missing, changed or not listed."""
    present = {
        path.relative_to(folder).as_posix()
        for path in folder.rglob("*")
        if path.is_file()
    }
    present.discard(MANIFEST)
    unlisted = sorted(present - set(manifest.files))
    if unlisted:
        raise PackRefusedError(
            "PACK_FILE_UNLISTED",
            f"{unlisted[0]} is in the pack but not in its manifest.",
        )
    total = 0
    for relative, expected in manifest.files.items():
        path = folder / relative
        if not path.is_file():
            raise PackRefusedError(
                "PACK_FILE_MISSING", f"{relative} is missing from the pack."
            )
        total += path.stat().st_size
        if total > MAX_PACK_BYTES:
            raise PackRefusedError("PACK_TOO_LARGE", "The pack is larger than 50 MB.")
        if sha256_of(path) != expected:
            raise PackRefusedError(
                "PACK_FILE_CHANGED",
                f"{relative} does not match its sha256 in the manifest.",
            )
