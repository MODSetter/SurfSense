"""A job pack's `job-pack.json`, read by the app's rules (contract 6), but taking any runner.

Which runners an app has is the selection's question, so a pack naming one the
server never heard of still passes here. Paths are held to the contract's rule,
which keeps to what Windows can write, since the app installs packs there too,
and a version to what the app may send back as the one it has installed: the
app holds both to the same rules, on every system.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from license.job_packs.schemas import RUNNER_PATTERN, VERSION_PATTERN

MANIFEST = "job-pack.json"
SIGNATURE = "job-pack.sig"
SCHEMA = "surfsense-job-pack/1"
_ID = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
# An installed pack's version goes back in every request as installed_version,
# which contract 6 holds to 1 to 9 digits a part, in the manifest as in the request.
_VERSION = re.compile(VERSION_PATTERN)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ENTITLEMENT = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_RUNNER = re.compile(RUNNER_PATTERN)
# Device names Windows reserves, with or without an extension. COM and LPT take the
# superscript one, two and three too, and never 0.
_PORT_DIGITS = "123456789\u00b9\u00b2\u00b3"
_RESERVED = frozenset(
    {"con", "prn", "aux", "nul", "conin$", "conout$"}
    | {f"com{digit}" for digit in _PORT_DIGITS}
    | {f"lpt{digit}" for digit in _PORT_DIGITS}
)
# Characters no Windows file name holds, beside the `\` and `:` every path refuses.
_UNWRITABLE = frozenset('<>"|?*') | frozenset(map(chr, range(32)))
# No disk holds a name part past 255 bytes, and a longer name costs its checks more.
_MAX_NAME_BYTES = 255
# How a Windows short name ends before its extension, as REPORT~1.MD does: Windows opens
# the file it is short for by that name, so it would be written over that file.
_SHORT_NAME = re.compile(r"~[0-9]+$")


class PackRefusedError(Exception):
    """A pack the server will not serve, with contract 6's code and a sentence for the log."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class PackJob:
    key: str
    runner: str
    # The license code that unlocks the job; every job of a paid pack has one.
    entitlement: str | None


@dataclass(frozen=True)
class PackManifest:
    id: str
    version: str
    access: str
    license_file: str
    jobs: tuple[PackJob, ...]
    files: dict[str, str]  # path inside the pack -> sha256


def version_key(version: str) -> tuple[int, int, int]:
    """Three integers, compared left to right: 1.10.0 is newer than 1.9.0."""
    major, minor, patch = (int(part) for part in version.split("."))
    return major, minor, patch


def parse_manifest(raw: object) -> PackManifest:
    if not isinstance(raw, dict) or raw.get("schema") != SCHEMA:
        raise PackRefusedError(
            "BAD_MANIFEST", f'{MANIFEST} must say "schema": "{SCHEMA}".'
        )
    pack_id = _text(raw, "id")
    if not _ID.fullmatch(pack_id):
        raise PackRefusedError(
            "BAD_MANIFEST", "id is lower-case letters, digits and dashes."
        )
    version = _text(raw, "version")
    if not _VERSION.fullmatch(version):
        raise PackRefusedError(
            "BAD_MANIFEST", "version is three numbers of 1 to 9 digits, like 1.0.0."
        )
    access = raw.get("access")
    if access not in ("free", "paid"):
        raise PackRefusedError("BAD_MANIFEST", 'access is "free" or "paid".')
    files = raw.get("files")
    if not isinstance(files, dict) or not files:
        raise PackRefusedError(
            "BAD_MANIFEST", "files lists every file with its sha256."
        )
    for path, digest in files.items():
        safe_path(path)
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise PackRefusedError(
                "BAD_MANIFEST", f"{path} needs a sha256 of 64 hex digits."
            )
    jobs = raw.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        raise PackRefusedError("BAD_MANIFEST", "jobs lists at least one job.")
    parsed = tuple(_job(job, files) for job in jobs)
    if len({job.key for job in parsed}) != len(parsed):
        raise PackRefusedError("BAD_MANIFEST", "Each job's key is used once.")
    license_file = _text(raw, "license_file")
    if license_file not in files:
        raise PackRefusedError(
            "BAD_MANIFEST", "license_file names a file the pack lists."
        )
    for field in ("name", "publisher", "description"):
        _text(raw, field)
    return PackManifest(
        id=pack_id,
        version=version,
        access=access,
        license_file=license_file,
        jobs=parsed,
        files=dict(files),
    )


def safe_path(path: object) -> PurePosixPath:
    """A relative path that stays inside the pack, in forward slashes, writable on Windows."""
    if not isinstance(path, str) or not path or "\\" in path or ":" in path:
        raise PackRefusedError("BAD_PATH", f"{path!r} is not a path inside the pack.")
    # First, so no check walks a longer name. A lone surrogate counts as its 3 bytes.
    if len(path.encode("utf-8", "surrogatepass")) > _MAX_NAME_BYTES:
        raise PackRefusedError(
            "BAD_PATH",
            f"{path[:60]!r}... is longer than {_MAX_NAME_BYTES} bytes in UTF-8.",
        )
    # Split as written: PurePosixPath drops empty and `.` parts, so a lone `.` has none.
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise PackRefusedError("BAD_PATH", f"{path!r} is not a path inside the pack.")
    if not _UNWRITABLE.isdisjoint(path):
        raise PackRefusedError(
            "BAD_PATH", f"{path!r} holds a character Windows cannot write."
        )
    for part in parts:
        # Windows reads `CON .txt` as CON: spaces before the extension do not count.
        device = part.split(".", 1)[0].rstrip(" ").casefold()
        if part.endswith((".", " ")) or device in _RESERVED:
            raise PackRefusedError(
                "BAD_PATH", f"{path!r} names a file Windows cannot write."
            )
        stem = part.rpartition(".")[0] if "." in part else part
        if _SHORT_NAME.search(stem):
            raise PackRefusedError(
                "BAD_PATH", f"{path!r} could be the Windows short name of another file."
            )
    return PurePosixPath(path)


def _job(raw: object, files: dict[str, str]) -> PackJob:
    if not isinstance(raw, dict):
        raise PackRefusedError("BAD_MANIFEST", "Each job is an object.")
    key = _text(raw, "key")
    if not _ID.fullmatch(key):
        raise PackRefusedError(
            "BAD_MANIFEST", "A job's key is lower-case letters, digits and dashes."
        )
    runner = _text(raw, "runner")
    if not _RUNNER.fullmatch(runner):
        raise PackRefusedError(
            "BAD_MANIFEST",
            f"Job {key}'s runner is a name and a version, like workbook-rows/1.",
        )
    config = _text(raw, "config")
    if config not in files:
        raise PackRefusedError(
            "BAD_MANIFEST", f"Job {key}'s config is not a file the pack lists."
        )
    skill = raw.get("skill")
    if skill is not None:
        folder = safe_path(skill)
        if f"{folder.as_posix()}/SKILL.md" not in files:
            raise PackRefusedError(
                "BAD_MANIFEST", f"Job {key}'s skill folder has no SKILL.md."
            )
        if not folder.name.startswith("surfsense-job-"):
            raise PackRefusedError(
                "BAD_MANIFEST", "A job skill's folder is named surfsense-job-<key>."
            )
    entitlement = raw.get("entitlement")
    if entitlement is not None and (
        not isinstance(entitlement, str) or not _ENTITLEMENT.fullmatch(entitlement)
    ):
        raise PackRefusedError(
            "BAD_MANIFEST",
            f"Job {key}'s entitlement is a license code in capitals, like JOB_QUESTIONNAIRE.",
        )
    _text(raw, "name")
    _text(raw, "description")
    return PackJob(key=key, runner=runner, entitlement=entitlement)


def _text(raw: dict, field: str) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise PackRefusedError("BAD_MANIFEST", f"{field} is missing from {MANIFEST}.")
    return value.strip()
