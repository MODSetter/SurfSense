"""The pack author's side: list every file of a pack folder with its sha256, and zip it.

Sealing changes the manifest, so a pack is signed after it is sealed, with the script that
holds SurfSense's pack key outside this repository; `zip` carries the signature along, and
refuses a folder without one or whose files differ from its manifest, as an install would.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from modules.jobs.packs.integrity import check_files, sha256_of
from modules.jobs.packs.manifest import (
    MANIFEST,
    SIGNATURE,
    PackRefusedError,
    parse_manifest,
)


def seal_pack(folder: Path) -> dict:
    """Rewrite the manifest's `files` from what the folder holds; returns the manifest."""
    path = folder / MANIFEST
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["files"] = {
        file.relative_to(folder).as_posix(): sha256_of(file)
        for file in sorted(folder.rglob("*"))
        if file.is_file()
        and file.relative_to(folder).as_posix() not in (MANIFEST, SIGNATURE)
    }
    parse_manifest(manifest)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def zip_pack(folder: Path, out: Path) -> Path:
    """The sealed pack as one file, its manifest at the top; a folder an install would refuse
    for its files or a missing signature writes nothing."""
    manifest = parse_manifest(
        json.loads((folder / MANIFEST).read_text(encoding="utf-8"))
    )
    if not (folder / SIGNATURE).is_file():
        raise PackRefusedError(
            "PACK_NOT_SIGNED",
            f"{SIGNATURE} is missing from {folder.name}: sign the sealed pack, then zip it.",
        )
    check_files(folder, manifest)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(folder / MANIFEST, MANIFEST)
        archive.write(folder / SIGNATURE, SIGNATURE)
        for relative in sorted(manifest.files):
            archive.write(folder / relative, relative)
    return out
