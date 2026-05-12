"""Description string for ``execute_code`` (mode-agnostic)."""

from __future__ import annotations

from app.agents.new_chat.filesystem_selection import FilesystemMode

_DESCRIPTION = """Executes Python code in an isolated sandbox environment.

Common data-science packages are pre-installed (pandas, numpy, matplotlib,
scipy, scikit-learn).

Usage notes:
- No outbound network access.
- Returns combined stdout/stderr with exit code.
- Use print() to produce output.
- Use the optional timeout parameter to override the default timeout.
"""


def select_description(mode: FilesystemMode) -> str:
    return _DESCRIPTION
