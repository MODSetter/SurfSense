"""Keep a git repository above the data folder from becoming the agent's project.

opencode takes the nearest `.git` above a thread's folder as its project, and
every folder inside the project as the agent's own. A `.git` file naming no
repository, beside the workspace's threads, is found first and fails git, so
opencode sees no repository, as when none is there.
"""

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.workspaces.models import Workspace
from shared.config import get_storage_settings

FENCE = ".git"
_NO_REPOSITORY = "gitdir: .git-none\n"


def fence_every_workspace(session: Session) -> None:
    """Fence each workspace's agent folder before opencode can open one of its folders.

    opencode resolves a folder's project once, when its instance starts, and a
    thread's history is read without its folder being synced.
    """
    storage = get_storage_settings()
    for workspace_id in session.scalars(select(Workspace.id)):
        fence_repository(storage.agent_working_dir(workspace_id))


def fence_repository(agent_working_dir: Path) -> None:
    """Write the fence only below a repository, so opencode runs no git where there is none.

    A folder already holding a `.git` keeps it.
    """
    fence = agent_working_dir / FENCE
    if fence.exists() or fence.is_symlink():
        return
    if not any((folder / FENCE).exists() for folder in agent_working_dir.parents):
        return
    agent_working_dir.mkdir(parents=True, exist_ok=True)
    fence.write_text(_NO_REPOSITORY, encoding="utf-8")
