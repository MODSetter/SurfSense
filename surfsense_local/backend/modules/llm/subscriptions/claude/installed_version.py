"""The version of the Claude Code installed, read once per binary as installed.

Read again only when the binary's path or modified time changes, so an update
or another `claude` found first is noticed without running it on every check.
"""

import subprocess
import sys
from pathlib import Path

# Without it, a windowless API flashes a console on Windows.
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
_read: dict[tuple[str, int], tuple[int, ...] | None] = {}


def installed_version(binary: Path) -> tuple[int, ...] | None:
    """None when it cannot be run or prints no version this code knows."""
    try:
        installed = (str(binary), binary.stat().st_mtime_ns)
    except OSError:
        return None
    if installed not in _read:
        _read[installed] = _version(binary)
    return _read[installed]


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
