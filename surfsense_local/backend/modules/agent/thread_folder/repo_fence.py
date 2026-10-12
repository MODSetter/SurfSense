"""Keep a git repository above the data folder from becoming the agent's project.

opencode takes the nearest `.git` above a thread's folder as its project, and
every folder inside the project as the agent's own. A `.git` file naming no
repository, beside the workspace's threads, is found first and fails git, so
opencode sees no repository, as when none is there.
"""

from pathlib import Path

FENCE = ".git"
_NO_REPOSITORY = "gitdir: .git-none\n"


def fence_repository(agent_working_dir: Path) -> None:
    """Write the fence once; a folder already holding a `.git` keeps it."""
    fence = agent_working_dir / FENCE
    if fence.exists() or fence.is_symlink():
        return
    agent_working_dir.mkdir(parents=True, exist_ok=True)
    fence.write_text(_NO_REPOSITORY, encoding="utf-8")
