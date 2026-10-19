import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from modules.llm.subscriptions.claude.launch import claude_env

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


def _run(binary: Path, *args: str, timeout: float, env: dict[str, str]) -> str:
    """Its answer, or nothing when it fails to give one in time."""
    try:
        return subprocess.run(
            [str(binary), *args],
            env=env,
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


def signed_in_account(
    binary: Path | None, *, timeout: float = 15, proxy_url: str | None = None
) -> str | None:
    """A digest of the plan account Claude Code is signed in to, or None when it reports none.

    A digest, since only a change matters and the email need not be kept.
    """
    if binary is None:
        return None
    env = {**os.environ, **claude_env(proxy_url)}
    auth = _sign_in(_run(binary, "auth", "status", timeout=timeout, env=env))
    if not auth.get("loggedIn") or auth.get("authMethod") != _PLAN_LOGIN:
        return None
    account = json.dumps([auth.get("email"), auth.get("orgId")])
    return hashlib.sha256(account.encode()).hexdigest()


def read_status(
    binary: Path | None, *, timeout: float = 15, proxy_url: str | None = None
) -> ClaudeStatus:
    """What the user's Claude Code reports about itself and its sign-in.

    Through SurfSense's proxy like every run: it contacts nothing today, and a
    later Claude Code that does is held to egress consent all the same.
    """
    if binary is None:
        return ClaudeStatus(ClaudeState.NOT_INSTALLED)
    env = {**os.environ, **claude_env(proxy_url)}
    match = re.search(
        r"(\d+)\.(\d+)\.(\d+)", _run(binary, "--version", timeout=timeout, env=env)
    )
    version = match.group() if match else None
    if match is None or tuple(int(n) for n in match.groups()) < MIN_VERSION:
        return ClaudeStatus(ClaudeState.TOO_OLD, version=version)
    auth = _sign_in(_run(binary, "auth", "status", timeout=timeout, env=env))
    if not auth.get("loggedIn") or auth.get("authMethod") != _PLAN_LOGIN:
        return ClaudeStatus(ClaudeState.SIGNED_OUT, version=version)
    return ClaudeStatus(
        ClaudeState.READY,
        version=version,
        email=auth.get("email"),
        plan=auth.get("subscriptionType"),
    )
