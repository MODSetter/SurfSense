"""Why Electron stopped starting opencode, as it leaves it in the agent folder."""

import json
from pathlib import Path

FAILURE_FILE = "opencode-failed.json"


def opencode_failure(agent_dir: Path, since: float) -> str | None:
    """The reason Electron gave up, when it gave up at or after `since` (a file time).

    An older file is from before this turn asked again, which earns opencode
    another start, so it says nothing yet.
    """
    path = agent_dir / FAILURE_FILE
    try:
        if path.stat().st_mtime < since:
            return None
        reason = json.loads(path.read_text("utf-8"))["reason"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return reason if isinstance(reason, str) else None
