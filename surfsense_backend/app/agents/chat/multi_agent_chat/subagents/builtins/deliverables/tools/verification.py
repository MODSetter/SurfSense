"""Sandbox-local verification state shared by deliverables tools."""

from __future__ import annotations

import json
import shlex
from dataclasses import dataclass

from app.sandbox import SandboxSession

LEDGER_PATH = "/tmp/.surfsense-verification"


@dataclass(frozen=True, slots=True)
class VerificationState:
    verified: bool
    reason: str | None = None


async def record_verification(
    session: SandboxSession, *, reason: str | None = None
) -> None:
    """Record the latest verification attempt using the sandbox's clock."""
    await session.write_file(
        LEDGER_PATH,
        json.dumps({"reason": reason}, separators=(",", ":")).encode(),
    )


async def check_verification(
    session: SandboxSession, artifact_path: str
) -> VerificationState:
    """Return whether the artifact predates the latest verification attempt."""
    artifact = shlex.quote(artifact_path)
    ledger = shlex.quote(LEDGER_PATH)
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
        payload = json.loads((await session.read_file(LEDGER_PATH)).decode())
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as exc:
        raise RuntimeError("Verification ledger is unreadable") from exc
    reason = payload.get("reason")
    return VerificationState(verified=reason is None, reason=reason)
