"""Install a job pack from a folder or a .zip into the app's data folder, one install at a time.

The copy is checked, its signature, its files and then the caller's own rules, before anything
installed changes. The new version is in place before the old one leaves, so a reader always
finds a version of the pack, and a refused pack leaves the installed one working.
"""

from __future__ import annotations

import errno
import logging
import shutil
import tempfile
import threading
import time
import zipfile
import zlib
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from modules.jobs.packs.installed import installed_packs
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

logger = logging.getLogger(__name__)

# Process-wide: a developer's packs, the path route, an import, a download and the daily check
# all install here, and two at once could each move the other's version away.
_INSTALLING = threading.Lock()
# What an install, a download or an import leaves when the app stops mid-way. Readers skip
# every name starting with a dot; an install sweeps these once they are an hour old.
_LEFTOVERS = (".installing-", ".replaced-", ".download-", ".upload-")
_LEFTOVER_SECONDS = 3600
# A pack's prompts, mappings and skill are a few dozen files; the count bounds the work too.
# Every member counts, a folder's own entry among them, as the licence server counts them.
MAX_MEMBERS = 1000
_FILE_KINDS = 0o170000
_SYMLINK = 0o120000
_READABLE = frozenset({zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED})
# What reading a damaged or hand-made zip raises, instead of a refusal.
_UNREADABLE = (
    zipfile.BadZipFile,
    zlib.error,
    EOFError,
    NotImplementedError,
    RuntimeError,
    UnicodeDecodeError,
    ValueError,
)
# What creating a member's file raises when its name, not the disk, is at fault: the zip's
# own rules refuse a file where a folder goes and the characters Windows cannot hold before
# anything is written, so this is the backstop for what else a system refuses, such as a
# name too long. A full disk stays an OSError: not written.
_NAME_ERRNOS = frozenset(
    {errno.EEXIST, errno.ENOTDIR, errno.EISDIR, errno.EINVAL, errno.ENAMETOOLONG}
)

# Called with the new pack's manifest and the newest verified version of each installed pack,
# before anything installed changes; it raises PackRefusedError to keep what is installed.
Accept = Callable[[PackManifest, list[PackManifest]], None]


def install_pack(
    source: Path,
    root: Path,
    *,
    accept: Accept | None = None,
    replace_same_version: bool = False,
) -> PackManifest:
    """The installed pack's manifest; `source` is a pack folder or a .zip of one, `root` the
    folder packs are installed in. Other contents at an installed version are refused unless
    `replace_same_version`, which only a developer's own paths ask for."""
    root.mkdir(parents=True, exist_ok=True)
    with (
        _INSTALLING,
        tempfile.TemporaryDirectory(
            prefix=".installing-", dir=root, ignore_cleanup_errors=True
        ) as scratch,
    ):
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
        if accept is not None:
            accept(manifest, [pack.manifest for pack in installed_packs(root)])
        _put_in_place(staged, raw, root, manifest, replace_same_version)
        _remove_leftovers(root)
    return manifest


def remove_pack(pack_id: str, root: Path) -> bool:
    """Whether a pack of that id was installed; its folder goes, the user's files stay."""
    folder = root / pack_id
    with _INSTALLING:
        if pack_id.startswith(".") or folder.parent != root or not folder.is_dir():
            return False
        shutil.rmtree(folder)
    return True


def _put_in_place(
    staged: Path,
    raw: object,
    root: Path,
    manifest: PackManifest,
    replace_same_version: bool,
) -> None:
    target = root / manifest.id / manifest.version
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        staged.rename(target)
    else:
        installed = _verified_raw(target)
        if installed is not None and installed != raw and not replace_same_version:
            raise PackRefusedError(
                "PACK_VERSION_TAKEN",
                f"Version {manifest.version} of {manifest.name} is already installed "
                "with other contents.",
            )
        if installed != raw:
            # A copy that fails its checks, which no reader lists, or a developer's
            # replacement: the version is missing for that moment only.
            aside = _aside(root)
            target.rename(aside)
            try:
                staged.rename(target)
            except OSError:
                # The installed copy goes back, so a failed replacement keeps it listed.
                with suppress(OSError):
                    aside.rename(target)
                raise
            shutil.rmtree(aside, ignore_errors=True)
    _remove_other_versions(root, manifest)


def _verified_raw(folder: Path) -> object | None:
    """The manifest of the pack in `folder` as read, when it passes its checks; else None."""
    try:
        raw = read_raw_manifest(folder)
        check_signature(folder, raw)
        check_files(folder, parse_manifest(raw))
    except (PackRefusedError, OSError):
        return None
    return raw


def _remove_other_versions(root: Path, manifest: PackManifest) -> None:
    """Every version but the one just put in place, each renamed out of the readers' sight first."""
    for other in sorted((root / manifest.id).iterdir()):
        if other.name == manifest.version or not other.is_dir():
            continue
        aside = _aside(root)
        try:
            other.rename(aside)
        except OSError as held:
            # On Windows a reader holding one of its files open blocks the move; the newest
            # is listed meanwhile, and the next install moves this one.
            logger.warning(
                "job pack %s %s left for the next install: %s",
                manifest.id,
                other.name,
                held,
            )
            continue
        shutil.rmtree(aside, ignore_errors=True)


def _aside(root: Path) -> Path:
    return root / f".replaced-{uuid4().hex}"


def _remove_leftovers(root: Path) -> None:
    cutoff = time.time() - _LEFTOVER_SECONDS
    for entry in root.iterdir():
        if not entry.name.startswith(_LEFTOVERS):
            continue
        try:
            if entry.stat().st_mtime > cutoff:
                continue
            if entry.is_dir():
                shutil.rmtree(entry, ignore_errors=True)
            else:
                entry.unlink()
        except OSError:
            continue


def _unzip(archive: Path, into: Path) -> None:
    """Extract only plain files at safe paths, within the caps; a folder named in the zip may
    wrap the pack. Contract 6's rules are checked on the zip's own list, the same on every
    system, before anything is written."""
    try:
        with zipfile.ZipFile(archive) as zipped:
            files = _files(zipped.infolist())
            prefix = _common_folder([member.filename for member in files])
            into.mkdir(parents=True)
            for member in files:
                name = member.filename
                path = into / (name[len(prefix) :] if prefix else name)
                with zipped.open(member) as source, _created(path, name) as copy:
                    shutil.copyfileobj(source, copy)
    except _UNREADABLE as broken:
        raise PackRefusedError(
            "NOT_A_PACK", f"{archive.name} is not a readable .zip."
        ) from broken


def _created(path: Path, name: str) -> BinaryIO:
    """The member's file, open for writing; a name no disk here can hold as the zip has it
    refuses the zip."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        return path.open("wb")
    except OSError as unwritable:
        # Windows answers a file written over a folder of that name with access denied.
        over_a_folder = isinstance(unwritable, PermissionError) and path.is_dir()
        if unwritable.errno not in _NAME_ERRNOS and not over_a_folder:
            raise
        raise PackRefusedError(
            "BAD_PATH", f"{name!r} cannot be written as a file on this computer."
        ) from unwritable


def _files(members: list[zipfile.ZipInfo]) -> list[zipfile.ZipInfo]:
    """The zip's files, once no member could be a bomb, a secret or a link, and every name,
    as the zip stores it, is in normal form and extracts as named on every system: a member's
    declared size bounds what reading it can produce. A folder's own entry is a member too,
    and carries nothing."""
    if len(members) > MAX_MEMBERS:
        # No pack holds that many, however small the zip: it is some other archive.
        raise PackRefusedError(
            "NOT_A_PACK",
            f"The zip holds more than {MAX_MEMBERS:,} files and folders, as no pack does.",
        )
    if sum(m.file_size for m in members) > MAX_PACK_BYTES:
        raise PackRefusedError("PACK_TOO_LARGE", "The pack is larger than 50 MB.")
    for member in members:
        if member.is_dir() and member.file_size:
            raise PackRefusedError(
                "NOT_A_PACK", f"{member.filename!r} is a folder that carries data."
            )
        if member.flag_bits & 0x1 or member.compress_type not in _READABLE:
            raise PackRefusedError(
                "NOT_A_PACK",
                f"{member.filename} is encrypted, or compressed as no pack is.",
            )
    for member in members:
        if (member.external_attr >> 16) & _FILE_KINDS == _SYMLINK:
            raise PackRefusedError(
                "BAD_PATH", f"{member.filename!r} is a link, not a file."
            )
    for member in members:
        # Read as stored: zipfile cuts a name at a NUL and, on Windows, reads a backslash as
        # a slash, so either would extract under a name the zip does not hold.
        stored = member.orig_filename
        path = stored[:-1] if member.is_dir() else stored
        if safe_path(path).as_posix() != path or stored != member.filename:
            raise PackRefusedError("BAD_PATH", f"{stored!r} is not in normal form.")
    # A folder's entry keeps its slash, so it is told apart from a file of its name.
    names = [member.filename for member in members]
    if len({name.casefold() for name in names}) != len(names):
        raise PackRefusedError(
            "BAD_PATH", "Two of the pack's names differ only in case."
        )
    _check_tree(names)
    return [member for member in members if not member.is_dir()]


def _check_tree(names: list[str]) -> None:
    """No folder spelled two ways but for case, and no file named as a folder of another
    member: neither extracts as named, on Windows or anywhere. Each name is walked a folder
    at a time, a folder known by the one above it and its own name: building every folder's
    whole name would cost the square of a name's depth, before any signature is read."""
    # (the number of the folder above, 0 for none; a part case-folded) -> (the folder's
    # number; that part as first spelled)
    folders: dict[tuple[int, str], tuple[int, str]] = {}
    for name in names:
        parts = name.removesuffix("/").split("/")
        held = parts if name.endswith("/") else parts[:-1]
        above = 0
        for depth, part in enumerate(held, start=1):
            above, spelled = folders.setdefault(
                (above, part.casefold()), (len(folders) + 1, part)
            )
            if spelled != part:
                # Every folder above is spelled as first seen, or the walk would have
                # stopped there: the first spelling differs in this part alone.
                folder = "/".join(held[:depth])
                first = "/".join([*held[: depth - 1], spelled])
                raise PackRefusedError(
                    "BAD_PATH",
                    f"The folder {folder!r} differs from {first!r} only in case.",
                )
    for name in names:
        if name.endswith("/"):
            continue
        *held, own = name.split("/")
        above = 0
        for part in held:
            above = folders[(above, part.casefold())][0]
        if (above, own.casefold()) in folders:
            raise PackRefusedError(
                "BAD_PATH", f"{name!r} is both a file and a folder of other members."
            )


def _common_folder(names: list[str]) -> str:
    """`pack/` when every file sits in one top folder holding the manifest, else nothing."""
    tops = {name.split("/", 1)[0] for name in names if "/" in name}
    if len(tops) == 1 and all("/" in name for name in names):
        top = next(iter(tops))
        if f"{top}/{MANIFEST}" in names:
            return f"{top}/"
    return ""
