"""The Claude Code a run may start: found, and not older than MIN_VERSION.

Asked before every run and by the chat model's check alike, so the composer and a
send never disagree. A version it cannot read is let through: an answer not yet
seen on another system must not block a plan that may work.
"""

from collections.abc import Callable
from pathlib import Path

from modules.llm.subscriptions.claude.errors import (
    ClaudeSignInRequiredError,
    ClaudeTooOldError,
)
from modules.llm.subscriptions.claude.installed_version import installed_version
from modules.llm.subscriptions.claude.locate import this_machines_claude
from modules.llm.subscriptions.claude.status import MIN_VERSION


def usable_claude(find: Callable[[], Path | None] = this_machines_claude) -> Path:
    """Runs `claude --version` only when the binary changed since it was last read."""
    binary = find()
    if binary is None:
        raise ClaudeSignInRequiredError("Claude Code is not installed")
    version = installed_version(binary)
    if version is not None and version < MIN_VERSION:
        raise ClaudeTooOldError(
            f"Claude Code {'.'.join(map(str, version))} is older than "
            f"{'.'.join(map(str, MIN_VERSION))}"
        )
    return binary
