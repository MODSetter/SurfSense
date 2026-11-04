"""Install a job pack from a folder or a .zip into the app's data folder, one version per pack.

The copy is checked, its signature and then its files, before it replaces what was
installed, so a refused pack leaves the installed one working.
"""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path

from modules.jobs.packs.integrity import MAX_PACK_BYTES, check_files
from modules.jobs.packs.manifest import (
    MANIFEST,
    PackManifest,
    PackRefusedError,
    parse_manifest,
    read_raw_manifest,
    safe_path,
)
from modules.jobs.packs.signature import check_signature


def install_pack(source: Path, root: Path) -> PackManifest:
    """The installed pack's manifest; `source` is a pack folder or a .zip of one,
    `root` the folder packs are installed in."""
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".installing-", dir=root) as scratch:
        staged = Path(scratch) / "pack"
        if source.is_dir():
            shutil.copytree(source, staged)
        elif zipfile.is_zipfile(source):
            _unzip(source, staged)
        else:
            raise PackRefusedError(
                "NOT_A_PACK", f"{source.name} is neither a pack folder nor a .zip."
            )
        raw = read_raw_manifest(staged)
        manifest = parse_manifest(raw)
        check_signature(staged, raw)
        check_files(staged, manifest)
        target = root / manifest.id / manifest.version
        old_versions = [p for p in (root / manifest.id).glob("*") if p.is_dir()]
        target.parent.mkdir(parents=True, exist_ok=True)
        for old in old_versions:
            shutil.rmtree(old)
        staged.rename(target)
    return manifest


def remove_pack(pack_id: str, root: Path) -> bool:
    """Whether a pack of that id was installed; its folder goes, the user's files stay."""
    folder = root / pack_id
    if pack_id.startswith(".") or folder.parent != root or not folder.is_dir():
        return False
    shutil.rmtree(folder)
    return True


def _unzip(archive: Path, into: Path) -> None:
    """Extract only plain files at safe paths; a folder named in the zip may wrap the pack."""
    with zipfile.ZipFile(archive) as zipped:
        members = [m for m in zipped.infolist() if not m.is_dir()]
        if sum(m.file_size for m in members) > MAX_PACK_BYTES:
            raise PackRefusedError("PACK_TOO_LARGE", "The pack is larger than 50 MB.")
        names = [safe_path(m.filename).as_posix() for m in members]
        prefix = _common_folder(names)
        into.mkdir(parents=True)
        for member, name in zip(members, names, strict=True):
            relative = name[len(prefix) :] if prefix else name
            path = into / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            with zipped.open(member) as source, path.open("wb") as copy:
                shutil.copyfileobj(source, copy)


def _common_folder(names: list[str]) -> str:
    """`pack/` when every file sits in one top folder holding the manifest, else nothing."""
    tops = {name.split("/", 1)[0] for name in names if "/" in name}
    if len(tops) == 1 and all("/" in name for name in names):
        top = next(iter(tops))
        if f"{top}/{MANIFEST}" in names:
            return f"{top}/"
    return ""
