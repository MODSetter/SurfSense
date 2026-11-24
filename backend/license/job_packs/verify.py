"""A zip is served only once it passes contract 6's zip section, as the app checks it and more strictly.

Checked in memory, member by member, in a fixed order; the first check that fails
names the refusal. A zip that cannot be read at all is refused too, never raised.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from dataclasses import dataclass, field

from license.job_packs.manifest import (
    MANIFEST,
    SIGNATURE,
    PackJob,
    PackManifest,
    PackRefusedError,
    parse_manifest,
    safe_path,
    version_key,
)
from license.job_packs.signature import (
    signature_lines,
    signed_by_every_line,
    signed_payload,
)

# The app's cap: room for prompts, mappings and a skill; a pack this large is not one.
MAX_PACK_BYTES = 50 * 1024 * 1024
MAX_MEMBERS = 1000
_FILE_TYPE = 0o170000
_SYMLINK = 0o120000
_ENCRYPTED = 0x1
_COMPRESSIONS = frozenset({zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED})


@dataclass(frozen=True)
class PublishedPack:
    """A pack that passed every check, and the bytes the route answers with."""

    id: str
    version: str
    jobs: tuple[PackJob, ...]
    data: bytes = field(repr=False)

    @property
    def filename(self) -> str:
        return f"{self.id}-{self.version}.zip"

    @property
    def version_key(self) -> tuple[int, int, int]:
        return version_key(self.version)

    @property
    def runners(self) -> frozenset[str]:
        return frozenset(job.runner for job in self.jobs)

    @property
    def entitlements(self) -> frozenset[str]:
        return frozenset(job.entitlement for job in self.jobs if job.entitlement)


def verified_pack(data: bytes, *, name: str) -> PublishedPack:
    """The pack `data` holds, published as `name`; PackRefusedError at the first failing check."""
    if len(data) > MAX_PACK_BYTES:
        raise PackRefusedError("PACK_TOO_LARGE", f"{name} is larger than 50 MB.")
    try:
        return _checked(data, name)
    except PackRefusedError:
        raise
    except Exception as unreadable:
        # zipfile's own errors, zlib's, a truncated stream, a name that is not UTF-8:
        # whatever reading raises, the pack is one nothing can serve.
        raise PackRefusedError(
            "NOT_A_PACK",
            f"{name} cannot be read as a zip ({type(unreadable).__name__}).",
        ) from unreadable


def _checked(data: bytes, name: str) -> PublishedPack:
    if not zipfile.is_zipfile(io.BytesIO(data)):
        raise PackRefusedError("NOT_A_PACK", f"{name} is not a zip.")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        _check_size(entries, name)
        _check_names(entries)
        _check_storage(entries)
        names = {entry.filename for entry in entries if not entry.is_dir()}
        if MANIFEST not in names:
            raise PackRefusedError(
                "NOT_A_PACK", f"{name} has no {MANIFEST} at its root."
            )
        if SIGNATURE not in names:
            raise PackRefusedError(
                "PACK_NOT_SIGNED", "The pack is not signed by SurfSense."
            )
        raw = _manifest_value(archive.read(MANIFEST))
        manifest = parse_manifest(raw)
        _check_signature(archive.read(SIGNATURE), raw)
        _check_files(archive, names, manifest)
    if manifest.access != "paid":
        raise PackRefusedError(
            "PACK_NOT_PAID", f"{name} is not a paid pack, the only kind served."
        )
    for job in manifest.jobs:
        if job.entitlement is None:
            raise PackRefusedError(
                "PACK_JOB_WITHOUT_ENTITLEMENT",
                f"Job {job.key} names no entitlement, so any license would get it.",
            )
    expected = f"{manifest.id}-{manifest.version}.zip"
    if name != expected:
        raise PackRefusedError(
            "PACK_NAME_MISMATCH",
            f"{name} holds {manifest.id} {manifest.version}, so its name must be {expected}.",
        )
    return PublishedPack(manifest.id, manifest.version, manifest.jobs, data)


def _check_size(entries: list[zipfile.ZipInfo], name: str) -> None:
    """Every member counts, folders among them, before any is looked at one by one."""
    if len(entries) > MAX_MEMBERS:
        raise PackRefusedError(
            "PACK_TOO_LARGE", f"{name} holds more than {MAX_MEMBERS:,} members."
        )
    if sum(entry.file_size for entry in entries) > MAX_PACK_BYTES:
        raise PackRefusedError(
            "PACK_TOO_LARGE", f"{name} holds more than 50 MB once extracted."
        )


def _check_names(entries: list[zipfile.ZipInfo]) -> None:
    """Names in normal form, no link, none equal to another but for case, and a tree
    that extracts as named.

    Read as stored: on Windows zipfile turns a backslash into a slash, and on
    every system it cuts a name at a NUL, so either would read as another name.
    """
    for entry in entries:
        stored = entry.orig_filename
        path = stored[:-1] if entry.is_dir() else stored
        if safe_path(path).as_posix() != path or stored != entry.filename:
            raise PackRefusedError("BAD_PATH", f"{stored!r} is not in normal form.")
    for entry in entries:
        if (entry.external_attr >> 16) & _FILE_TYPE == _SYMLINK:
            raise PackRefusedError("BAD_PATH", f"{entry.filename!r} is a link.")
    seen: set[str] = set()
    for entry in entries:
        folded = entry.filename.casefold()
        if folded in seen:
            raise PackRefusedError(
                "BAD_PATH",
                f"{entry.filename!r} differs from another name only in case.",
            )
        seen.add(folded)
    _check_tree(entries)


def _check_tree(entries: list[zipfile.ZipInfo]) -> None:
    """No folder spelled two ways but for case, and no file named as a folder of another:
    neither extracts as named, on Windows or anywhere."""
    folders: dict[str, str] = {}  # case-folded, to as first spelled
    for entry in entries:
        parts = entry.filename.rstrip("/").split("/")
        held = parts if entry.is_dir() else parts[:-1]
        for depth in range(1, len(held) + 1):
            folder = "/".join(held[:depth])
            spelled = folders.setdefault(folder.casefold(), folder)
            if spelled != folder:
                raise PackRefusedError(
                    "BAD_PATH",
                    f"The folder {folder!r} differs from {spelled!r} only in case.",
                )
    for entry in entries:
        if not entry.is_dir() and entry.filename.casefold() in folders:
            raise PackRefusedError(
                "BAD_PATH",
                f"{entry.filename!r} is both a file and a folder of other members.",
            )


def _check_storage(entries: list[zipfile.ZipInfo]) -> None:
    for entry in entries:
        if entry.is_dir() and entry.file_size:
            raise PackRefusedError(
                "NOT_A_PACK", f"{entry.filename!r} is a folder that carries data."
            )
        if entry.flag_bits & _ENCRYPTED:
            raise PackRefusedError("NOT_A_PACK", f"{entry.filename!r} is encrypted.")
        if entry.compress_type not in _COMPRESSIONS:
            raise PackRefusedError(
                "NOT_A_PACK", f"{entry.filename!r} is neither stored nor deflated."
            )


def _manifest_value(raw: bytes) -> object:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as broken:
        raise PackRefusedError("BAD_MANIFEST", f"{MANIFEST} is not UTF-8.") from broken
    if text.startswith("﻿"):
        raise PackRefusedError(
            "BAD_MANIFEST", f"{MANIFEST} starts with a byte-order mark."
        )
    try:
        return json.loads(text)
    except (ValueError, RecursionError) as broken:
        raise PackRefusedError(
            "BAD_MANIFEST", f"{MANIFEST} is not readable JSON."
        ) from broken


def _check_signature(raw: bytes, manifest: object) -> None:
    signatures = signature_lines(raw)
    try:
        payload = signed_payload(manifest)
    # A lone surrogate cannot be written as UTF-8 (a ValueError): no key signed it.
    except (ValueError, TypeError, RecursionError) as broken:
        raise PackRefusedError(
            "PACK_BAD_SIGNATURE", "The pack's signature cannot be read."
        ) from broken
    if not signed_by_every_line(payload, signatures):
        raise PackRefusedError(
            "PACK_BAD_SIGNATURE",
            "A line of job-pack.sig is not SurfSense's signature of this manifest: "
            "the pack changed after it was signed, or SurfSense did not sign it.",
        )


def _check_files(
    archive: zipfile.ZipFile, names: set[str], manifest: PackManifest
) -> None:
    listed = set(manifest.files)
    unlisted = sorted(names - {MANIFEST, SIGNATURE} - listed)
    if unlisted:
        raise PackRefusedError(
            "PACK_FILE_UNLISTED",
            f"{unlisted[0]} is in the pack but not in its manifest.",
        )
    missing = sorted(listed - names)
    if missing:
        raise PackRefusedError(
            "PACK_FILE_MISSING", f"{missing[0]} is missing from the pack."
        )
    for path, expected in sorted(manifest.files.items()):
        if hashlib.sha256(archive.read(path)).hexdigest() != expected:
            raise PackRefusedError(
                "PACK_FILE_CHANGED",
                f"{path} does not match its sha256 in the manifest.",
            )
