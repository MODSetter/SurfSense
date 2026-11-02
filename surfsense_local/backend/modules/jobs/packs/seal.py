"""The pack author's side: list every file of a pack folder with its sha256, and zip it."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from modules.jobs.packs.integrity import sha256_of
from modules.jobs.packs.manifest import MANIFEST, parse_manifest


def seal_pack(folder: Path) -> dict:
    """Rewrite the manifest's `files` from what the folder holds; returns the manifest."""
    path = folder / MANIFEST
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["files"] = {
        file.relative_to(folder).as_posix(): sha256_of(file)
        for file in sorted(folder.rglob("*"))
        if file.is_file() and file.name != MANIFEST
    }
    parse_manifest(manifest)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def zip_pack(folder: Path, out: Path) -> Path:
    """The sealed pack as one file, its manifest at the top."""
    manifest = parse_manifest(
        json.loads((folder / MANIFEST).read_text(encoding="utf-8"))
    )
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(folder / MANIFEST, MANIFEST)
        for relative in sorted(manifest.files):
            archive.write(folder / relative, relative)
    return out
