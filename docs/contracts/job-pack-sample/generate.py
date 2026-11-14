#!/usr/bin/env python3
"""Write contract 6's sample pack, signed by a test key no release trusts, then check it.

    cd backend && uv run python ../docs/contracts/job-pack-sample/generate.py

Needs the standard library and `cryptography`. The key comes from a fixed seed
and Ed25519 signs deterministically, so a re-run writes the same bytes.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import sys
import zipfile
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

HERE = Path(__file__).resolve().parent
ZIP_NAME = "sample-jobs-1.0.0.zip"
SEED = b"surfsense-contract-6-test-seed!!"
DOMAIN = b"surfsense-job-pack/1\n"
FILES = {
    "LICENSE.txt": b"Test pack for contract 6. Not for use.\n",
    "jobs/sample-questionnaire/job.json": b"{}\n",
}
MANIFEST = {
    "schema": "surfsense-job-pack/1",
    "id": "sample-jobs",
    "version": "1.0.0",
    "name": "Sample jobs",
    "publisher": "SurfSense contract 6",
    "description": "A made-up pack for contract 6's tests.",
    "access": "paid",
    "license_file": "LICENSE.txt",
    "jobs": [
        {
            "key": "sample-questionnaire",
            "name": "Sample questionnaire",
            "description": "A made-up job.",
            "runner": "workbook-rows/1",
            "config": "jobs/sample-questionnaire/job.json",
            "entitlement": "JOB_QUESTIONNAIRE",
        }
    ],
    "files": {
        path: hashlib.sha256(data).hexdigest() for path, data in sorted(FILES.items())
    },
}
FIRST_MEMBERS = ("job-pack.json", "job-pack.sig")
MAX_MEMBERS = 1000
# No name holds these, beside the `\` and `:` every name refuses.
UNWRITABLE = frozenset('<>"|?*') | frozenset(map(chr, range(32)))
VERSION = re.compile(r"^[0-9]{1,9}\.[0-9]{1,9}\.[0-9]{1,9}$")


def signed_payload(manifest: object) -> bytes:
    """What a signature covers: the domain, then the manifest as canonical JSON."""
    canonical = json.dumps(
        manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return DOMAIN + canonical.encode("utf-8")


def sample_zip(
    key: Ed25519PrivateKey,
    *,
    written: dict = MANIFEST,
    signed: dict = MANIFEST,
    files: dict[str, bytes] = FILES,
) -> bytes:
    """The pack, stored, manifest and signature first; `written` and `signed` differ only
    in a self-check, as do `files`."""
    members = [
        ("job-pack.json", (json.dumps(written, indent=2) + "\n").encode("utf-8")),
        ("job-pack.sig", base64.b64encode(key.sign(signed_payload(signed))) + b"\n"),
        *sorted(files.items()),
    ]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
        for name, data in members:
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 3, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)
    return buffer.getvalue()


def problems(data: bytes, public_key: Ed25519PublicKey) -> list[str]:
    """What breaks contract 6's zip section, enough to catch this generator drifting."""
    found = []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        files = [entry.filename for entry in entries if not entry.is_dir()]
        if len(entries) > MAX_MEMBERS:
            found.append(f"the zip holds more than {MAX_MEMBERS:,} members")
        folders: dict[str, str] = {}  # case-folded, to as first spelled
        for entry in entries:
            # A directory entry's name ends in a slash, which is not a part.
            path = entry.filename[:-1] if entry.is_dir() else entry.filename
            parts = path.split("/")
            if (
                entry.compress_type != zipfile.ZIP_STORED
                or entry.flag_bits & 0x1
                or "\\" in path
                or ":" in path
                or not UNWRITABLE.isdisjoint(path)
                or any(p in ("", ".", "..") or p.endswith((".", " ")) for p in parts)
            ):
                found.append(f"{entry.filename} is not a plain, safely named member")
            if entry.is_dir() and entry.file_size:
                found.append(f"{entry.filename} is a folder that carries data")
            held = parts if entry.is_dir() else parts[:-1]
            for depth in range(1, len(held) + 1):
                folder = "/".join(held[:depth])
                if folders.setdefault(folder.casefold(), folder) != folder:
                    found.append(f"the folder {folder} is spelled two ways")
        for name in files:
            if name.casefold() in folders:
                found.append(f"{name} is also the folder of another member")
        if names[:2] != list(FIRST_MEMBERS):
            found.append("the manifest and the signature are not the first members")
        raw = archive.read("job-pack.json")
        if raw.startswith(b"\xef\xbb\xbf"):
            found.append("the manifest starts with a byte-order mark")
        manifest = json.loads(raw.decode("utf-8"))
        if not VERSION.fullmatch(str(manifest["version"])):
            found.append("the version is not x.y.z with 1 to 9 digits a part")
        lines = [
            line for line in archive.read("job-pack.sig").splitlines() if line.strip()
        ]
        if len(lines) != 1:
            found.append(f"the signature has {len(lines)} lines, not one")
        for line in lines:
            try:
                public_key.verify(
                    base64.b64decode(line, validate=True), signed_payload(manifest)
                )
            except (InvalidSignature, ValueError):
                found.append("a signature line does not verify")
        if set(files) - set(FIRST_MEMBERS) != set(manifest["files"]):
            found.append("the files listed are not the zip's other members")
        for path, digest in manifest["files"].items():
            if (
                path in files
                and hashlib.sha256(archive.read(path)).hexdigest() != digest
            ):
                found.append(f"{path} does not match its sha256")
        if manifest["access"] != "paid" or not all(
            job.get("entitlement") for job in manifest["jobs"]
        ):
            found.append("the pack is not paid, or a job has no entitlement")
    return found


def main() -> int:
    key = Ed25519PrivateKey.from_private_bytes(SEED)
    public_key = key.public_key()
    data = sample_zip(key)
    (HERE / ZIP_NAME).write_bytes(data)
    public_hex = public_key.public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    (HERE / "public-key.hex").write_text(
        public_hex + "\n", encoding="ascii", newline="\n"
    )

    errors = problems(data, public_key)
    one_byte = FILES["LICENSE.txt"].replace(b"use.\n", b"use!\n")
    changed_file = sample_zip(key, files={**FILES, "LICENSE.txt": one_byte})
    if not any("sha256" in found for found in problems(changed_file, public_key)):
        errors.append("a changed byte in a listed file passed its sha256")
    changed_manifest = sample_zip(key, written={**MANIFEST, "version": "1.0.1"})
    if not any("verify" in found for found in problems(changed_manifest, public_key)):
        errors.append("a changed manifest passed the signature")

    for error in errors:
        print(error, file=sys.stderr)
    if errors:
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
