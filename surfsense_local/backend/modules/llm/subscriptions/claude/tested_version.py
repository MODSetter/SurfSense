"""Which Claude Code SurfSense was last measured against, so a newer one is named in the log.

What docs/architecture/claude-plan.md states of Claude Code was measured on one
version; a newer one may change it without notice, and nothing offline can tell.
"""

import logging
from pathlib import Path

from modules.llm.subscriptions.claude.installed_version import installed_version

logger = logging.getLogger(__name__)

# The newest Claude Code the `claude_code` tests passed on (17 Oct 2026): raise it only
# once they pass again, `SURFSENSE_CLAUDE_CODE_TESTS=1 uv run pytest -m claude_code`.
NEWEST_TESTED = (2, 1, 301)

# Each version is named once: every run checks.
_noted: set[tuple[int, ...]] = set()


def note_untested(binary: Path) -> None:
    """Warn once per version when it is newer than NEWEST_TESTED."""
    version = installed_version(binary)
    if version is None or version <= NEWEST_TESTED or version in _noted:
        return
    _noted.add(version)
    logger.warning(
        "Claude Code %s is newer than %s, the newest SurfSense was tested on; "
        "what docs/architecture/claude-plan.md measured may have changed",
        ".".join(map(str, version)),
        ".".join(map(str, NEWEST_TESTED)),
    )
