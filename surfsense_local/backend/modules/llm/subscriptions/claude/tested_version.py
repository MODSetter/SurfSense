"""Which Claude Code SurfSense was last measured against, so a newer one is named in the log.

What docs/architecture/claude-plan.md states of Claude Code was measured on one
version; a newer one may change it without notice, and nothing offline can tell.
"""

import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# The newest Claude Code the `claude_code` tests passed on (17 Oct 2026): raise it only
# once they pass again, `SURFSENSE_CLAUDE_CODE_TESTS=1 uv run pytest -m claude_code`.
NEWEST_TESTED = (2, 1, 301)

# Without it, a windowless API flashes a console on Windows.
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
# Each binary, as installed, is named once: every run checks.
_noted: set[tuple[str, int]] = set()


def note_untested(binary: Path) -> None:
    """Warn once per installed binary when it is newer than NEWEST_TESTED."""
    try:
        installed = (str(binary), binary.stat().st_mtime_ns)
    except OSError:
        return
    if installed in _noted:
        return
    _noted.add(installed)
    version = _version(binary)
    if version is not None and version > NEWEST_TESTED:
        logger.warning(
            "Claude Code %s is newer than %s, the newest SurfSense was tested on; "
            "what docs/architecture/claude-plan.md measured may have changed",
            ".".join(map(str, version)),
            ".".join(map(str, NEWEST_TESTED)),
        )


def _version(binary: Path) -> tuple[int, ...] | None:
    try:
        printed = subprocess.run(
            [str(binary), "--version"],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=_NO_WINDOW,
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    # Printed as "2.1.301 (Claude Code)".
    first = printed.split(maxsplit=1)[0] if printed.strip() else ""
    parts = first.split(".")
    if not all(part.isdigit() for part in parts) or len(parts) != 3:
        return None
    return tuple(int(part) for part in parts)
