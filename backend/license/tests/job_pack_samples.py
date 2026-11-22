"""Job packs made for the tests, signed with a test key no release trusts."""

from __future__ import annotations

import base64
import copy
import hashlib
import io
import json
import struct
import zipfile
from collections.abc import Callable, Iterable
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from license.job_packs.signature import signed_payload

TEST_PACK_KEY = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))


def public_hex(key: Ed25519PrivateKey) -> str:
    return key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()


TEST_PACK_PUBLIC_KEY_HEX = public_hex(TEST_PACK_KEY)

# key, runner, entitlement (None for a job without one)
Job = tuple[str, str, str | None]
QUESTIONNAIRE: Job = ("sample-questionnaire", "workbook-rows/1", "JOB_QUESTIONNAIRE")
# A name, written as given, or a ZipInfo carrying its own attributes.
Member = tuple[str | zipfile.ZipInfo, bytes]

_DATE = (2026, 11, 3, 0, 0, 0)


def pack_zip(
    *,
    pack_id: str = "sample-jobs",
    version: str = "1.0.0",
    jobs: Iterable[Job] = (QUESTIONNAIRE,),
    access: str = "paid",
    keys: Iterable[Ed25519PrivateKey] = (TEST_PACK_KEY,),
    sig_lines: Iterable[bytes] | None = None,
    extra_members: Iterable[Member] = (),
    manifest_edit: Callable[[dict], None] | None = None,
    wrap_folder: str | None = None,
    member_edit: Callable[[str, bytes], bytes] | None = None,
    compression: int = zipfile.ZIP_STORED,
) -> bytes:
    """A sealed pack, one signature line per key; no `job-pack.sig` without keys or lines.

    `manifest_edit` changes the manifest before it is signed, `member_edit` a member's
    bytes after, `sig_lines` replaces the signature's lines.
    """
    files = {"LICENSE.txt": b"Test pack for the license server. Not for use.\n"}
    entries = []
    for key, runner, entitlement in jobs:
        config = f"jobs/{key}/job.json"
        files[config] = b"{}\n"
        job = {
            "key": key,
            "name": key.replace("-", " ").capitalize(),
            "description": "A made-up job.",
            "runner": runner,
            "config": config,
        }
        if entitlement is not None:
            job["entitlement"] = entitlement
        entries.append(job)
    manifest: dict = {
        "schema": "surfsense-job-pack/1",
        "id": pack_id,
        "version": version,
        "name": "Sample jobs",
        "publisher": "SurfSense tests",
        "description": "A made-up pack for the license server's tests.",
        "access": access,
        "license_file": "LICENSE.txt",
        "jobs": entries,
        "files": {
            path: hashlib.sha256(data).hexdigest()
            for path, data in sorted(files.items())
        },
    }
    if manifest_edit is not None:
        manifest_edit(manifest)

    members: list[Member] = [
        ("job-pack.json", (json.dumps(manifest, indent=2) + "\n").encode())
    ]
    signers = tuple(keys)
    if sig_lines is None and signers:
        payload = signed_payload(manifest)
        sig_lines = [base64.b64encode(key.sign(payload)) for key in signers]
    if sig_lines is not None:
        members.append(("job-pack.sig", b"".join(line + b"\n" for line in sig_lines)))
    members += sorted(files.items())
    members += list(extra_members)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in members:
            # Writing fills a ZipInfo in, so a caller's is copied first.
            info = (
                copy.copy(name) if isinstance(name, zipfile.ZipInfo) else _plain(name)
            )
            if wrap_folder is not None:
                info.filename = f"{wrap_folder}/{info.filename}"
            if not isinstance(name, zipfile.ZipInfo):
                info.compress_type = compression
            if member_edit is not None:
                data = member_edit(info.filename, data)
            archive.writestr(info, data)
    return buffer.getvalue()


def _plain(name: str) -> zipfile.ZipInfo:
    """A regular file under exactly this name: ZipInfo would turn a backslash into a slash."""
    info = zipfile.ZipInfo("member", date_time=_DATE)
    info.filename = name
    info.create_system = 3
    info.external_attr = 0o644 << 16
    return info


def write_pack(folder: Path, *, name: str | None = None, **kw) -> Path:
    """`pack_zip(**kw)` as `<id>-<version>.zip` in `folder`, or as `name`."""
    pack_id = kw.get("pack_id", "sample-jobs")
    version = kw.get("version", "1.0.0")
    path = folder / (name or f"{pack_id}-{version}.zip")
    path.write_bytes(pack_zip(**kw))
    return path


def symlink(name: str, target: str) -> Member:
    info = zipfile.ZipInfo("member", date_time=_DATE)
    info.filename = name
    info.create_system = 3
    info.external_attr = 0o120777 << 16
    return info, target.encode()


def corrupt_member(data: bytes, member: str) -> bytes:
    """`member`'s compressed bytes overwritten, as a broken download leaves them."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        info = archive.getinfo(member)
    raw = bytearray(data)
    name_length, extra_length = struct.unpack_from("<HH", raw, info.header_offset + 26)
    start = info.header_offset + 30 + name_length + extra_length
    raw[start : start + info.compress_size] = b"\xff" * info.compress_size
    return bytes(raw)


def encrypted(data: bytes, member: str) -> bytes:
    """`member` flagged as encrypted in both its headers; zipfile never writes the flag."""
    raw = bytearray(data)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        raw[archive.getinfo(member).header_offset + 6] |= 0x01
    central = raw.find(b"PK\x01\x02")
    while central != -1:
        (name_length,) = struct.unpack_from("<H", raw, central + 28)
        if raw[central + 46 : central + 46 + name_length] == member.encode():
            raw[central + 8] |= 0x01
        central = raw.find(b"PK\x01\x02", central + 4)
    return bytes(raw)


def with_name_bytes(data: bytes, name: str, raw_name: bytes) -> bytes:
    """`name` written as `raw_name`, of the same length, wherever the zip holds it."""
    encoded = name.encode()
    assert len(encoded) == len(raw_name)
    return data.replace(encoded, raw_name)
