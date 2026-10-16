import json
import re
import subprocess
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

# The oldest Claude Code the Claude plan was measured against (16 Oct 2026).
MIN_VERSION = (2, 1, 300)
# A Console login bills an API account, not a plan.
_PLAN_LOGIN = "claude.ai"


class ClaudeState(StrEnum):
    NOT_INSTALLED = "not_installed"
    TOO_OLD = "too_old"
    SIGNED_OUT = "signed_out"
    READY = "ready"


@dataclass(frozen=True)
class ClaudeStatus:
    state: ClaudeState
    version: str | None = None
    email: str | None = None
    plan: str | None = None


# Without it, a windowless API flashes a console for every check on Windows.
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def _run(binary: Path, *args: str, timeout: float) -> str:
    """Its answer, or nothing when it fails to give one in time."""
    try:
        return subprocess.run(
            [str(binary), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=_NO_WINDOW,
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _sign_in(text: str) -> dict:
    try:
        answer = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return answer if isinstance(answer, dict) else {}


def read_status(binary: Path | None, *, timeout: float = 15) -> ClaudeStatus:
    """What the user's Claude Code reports about itself and its sign-in."""
    if binary is None:
        return ClaudeStatus(ClaudeState.NOT_INSTALLED)
    match = re.search(
        r"(\d+)\.(\d+)\.(\d+)", _run(binary, "--version", timeout=timeout)
    )
    version = match.group() if match else None
    if match is None or tuple(int(n) for n in match.groups()) < MIN_VERSION:
        return ClaudeStatus(ClaudeState.TOO_OLD, version=version)
    auth = _sign_in(_run(binary, "auth", "status", timeout=timeout))
    if not auth.get("loggedIn") or auth.get("authMethod") != _PLAN_LOGIN:
        return ClaudeStatus(ClaudeState.SIGNED_OUT, version=version)
    return ClaudeStatus(
        ClaudeState.READY,
        version=version,
        email=auth.get("email"),
        plan=auth.get("subscriptionType"),
    )
