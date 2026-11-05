"""A job pack's `job-pack.json`: who it is, the jobs it adds, and every file's sha256.

A pack is data the app's runners read (prompts, mappings, rules, a skill), never
code the app runs, so installing one needs no process, sandbox or interpreter.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

MANIFEST = "job-pack.json"
# SurfSense's signature over the manifest, beside it and, like it, not one of its files.
SIGNATURE = "job-pack.sig"
SCHEMA = "surfsense-job-pack/1"
# The runners this app ships; a pack naming another needs a newer app.
RUNNERS = ("workbook-rows/1",)
_ID = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_VERSION = re.compile(r"^\d+\.\d+\.\d+$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
# A licence entitlement code, as the licence server names one: JOB_QUESTIONNAIRE.
_ENTITLEMENT = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")

Access = Literal["free", "paid"]


class PackRefusedError(Exception):
    """A pack the app will not install or run, with a code and a sentence for the user."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class PackJob:
    key: str
    name: str
    description: str
    runner: str
    config: str  # the runner's settings, a file in the pack
    skill: str | None  # a folder holding the job skill's SKILL.md, named as the skill
    # The licence entitlement that unlocks a paid pack's job, carried in a licence's jobs.
    entitlement: str | None = None


@dataclass(frozen=True)
class PackManifest:
    id: str
    version: str
    name: str
    publisher: str
    description: str
    access: Access
    license_file: str
    jobs: tuple[PackJob, ...]
    files: dict[str, str]  # path inside the pack -> sha256


def read_manifest(folder: Path) -> PackManifest:
    return parse_manifest(read_raw_manifest(folder))


def read_raw_manifest(folder: Path) -> object:
    """The manifest as read, once: what the signature is checked against is what is used."""
    try:
        return json.loads((folder / MANIFEST).read_text(encoding="utf-8"))
    except FileNotFoundError as missing:
        raise PackRefusedError(
            "NOT_A_PACK", f"No {MANIFEST} in {folder.name}."
        ) from missing
    except (OSError, ValueError, RecursionError) as broken:
        raise PackRefusedError(
            "BAD_MANIFEST", f"{MANIFEST} is not readable JSON."
        ) from broken


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
        raise PackRefusedError("BAD_MANIFEST", "version is three numbers, like 1.0.0.")
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
    return PackManifest(
        id=pack_id,
        version=version,
        name=_text(raw, "name"),
        publisher=_text(raw, "publisher"),
        description=_text(raw, "description"),
        access=access,
        license_file=license_file,
        jobs=parsed,
        files=dict(files),
    )


def safe_path(path: object) -> PurePosixPath:
    """A relative path that stays inside the pack, in forward slashes."""
    if not isinstance(path, str) or not path or "\\" in path or ":" in path:
        raise PackRefusedError("BAD_PATH", f"{path!r} is not a path inside the pack.")
    pure = PurePosixPath(path)
    if pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts):
        raise PackRefusedError("BAD_PATH", f"{path!r} is not a path inside the pack.")
    return pure


def _job(raw: object, files: dict[str, str]) -> PackJob:
    if not isinstance(raw, dict):
        raise PackRefusedError("BAD_MANIFEST", "Each job is an object.")
    key = _text(raw, "key")
    if not _ID.fullmatch(key):
        raise PackRefusedError(
            "BAD_MANIFEST", "A job's key is lower-case letters, digits and dashes."
        )
    runner = _text(raw, "runner")
    if runner not in RUNNERS:
        raise PackRefusedError(
            "NEEDS_NEWER_APP",
            f"Job {key} needs the {runner} runner, which this app does not have.",
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
            f"Job {key}'s entitlement is a licence code in capitals, like JOB_QUESTIONNAIRE.",
        )
    return PackJob(
        key=key,
        name=_text(raw, "name"),
        description=_text(raw, "description"),
        runner=runner,
        config=config,
        skill=skill,
        entitlement=entitlement,
    )


def _text(raw: dict, field: str) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise PackRefusedError("BAD_MANIFEST", f"{field} is missing from {MANIFEST}.")
    return value.strip()
