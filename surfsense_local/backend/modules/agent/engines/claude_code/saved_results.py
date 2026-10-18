"""Where Claude Code saves a tool result too large to give the model whole.

It writes the result under `<config home>/projects/<project>/<session id>/tool-results/`
and gives the model a preview and that path, as opencode keeps long output in
its tool-output folder. Only the turn's own session is ever read from there.
"""

import os
from pathlib import Path

_RESULTS = "tool-results"


def claude_home() -> Path:
    """Claude Code's config folder, as it finds it itself."""
    configured = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(configured) if configured else Path.home() / ".claude"


def is_saved_result(path: Path, home: Path, session_id: str) -> bool:
    """Whether `path`, already resolved, is in this session's saved results."""
    projects = (home / "projects").resolve()
    if not path.is_relative_to(projects):
        return False
    parts = path.relative_to(projects).parts
    # <project>/<session id>/tool-results[/...]: the project key is Claude Code's
    # spelling of the working folder, so the session id is what is checked.
    return len(parts) >= 3 and parts[1] == session_id and parts[2] == _RESULTS
