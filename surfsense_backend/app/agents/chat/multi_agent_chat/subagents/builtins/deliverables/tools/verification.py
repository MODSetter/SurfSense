"""Sandbox-local verification state shared by deliverables tools."""

from __future__ import annotations

import json
import shlex
from dataclasses import dataclass
from typing import Literal

from app.sandbox import SandboxSession

VerificationKind = Literal["structural", "visual"]


def ledger_path(kind: VerificationKind) -> str:
    """Where a kind of verification is recorded.

    Each kind gets its own file because freshness is the ledger's own mtime: one
    shared file would only ever prove whichever kind was written last, so a
    re-run of the checker after a vision pass would erase the vision pass.
    """
    return f"/tmp/.surfsense-verification-{kind}"


@dataclass(frozen=True, slots=True)
class VerificationState:
    verified: bool
    reason: str | None = None
    # The file a structural script named in its sentinel. Visual receipts name
    # rendered pages rather than the artifact, so they carry no path.
    path: str | None = None


async def record_verification(
    session: SandboxSession,
    kind: VerificationKind,
    *,
    reason: str | None = None,
    path: str | None = None,
) -> None:
    """Record the latest verification of a kind using the sandbox's clock."""
    await session.write_file(
        ledger_path(kind),
        json.dumps({"reason": reason, "path": path}, separators=(",", ":")).encode(),
    )


async def check_verification(
    session: SandboxSession, artifact_path: str, kind: VerificationKind
) -> VerificationState:
    """Return whether the artifact predates the latest verification of a kind."""
    artifact = shlex.quote(artifact_path)
    ledger = shlex.quote(ledger_path(kind))
    result = await session.run_command(
        f"if [ ! -e {artifact} ]; then printf ARTIFACT_MISSING; "
        f"elif [ ! -e {ledger} ]; then printf MISSING; "
        f"elif [ \"$(stat -c %Y -- {artifact})\" -gt "
        f"\"$(stat -c %Y -- {ledger})\" ]; then printf STALE; "
        "else printf CURRENT; fi"
    )
    status = result.output.strip()
    if not result.ok:
        raise FileNotFoundError(f"Could not stat artifact file: {artifact_path}")
    if status == "ARTIFACT_MISSING":
        raise FileNotFoundError(f"Artifact file does not exist: {artifact_path}")
    if status == "MISSING":
        return VerificationState(verified=False)
    if status == "STALE":
        return VerificationState(verified=False)
    if status != "CURRENT":
        raise RuntimeError(f"Unexpected verification status: {status}")

    try:
        payload = json.loads((await session.read_file(ledger_path(kind))).decode())
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as exc:
        raise RuntimeError("Verification ledger is unreadable") from exc
    reason = payload.get("reason")
    return VerificationState(
        verified=reason is None, reason=reason, path=payload.get("path")
    )
