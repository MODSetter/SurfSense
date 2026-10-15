"""Once per workspace per run: drop the folder every thread once shared, and any dead thread's.

`agent/outputs/` outside its previews stays: the app shows it nowhere, and it
leaves with the workspace.
"""

import shutil
import threading
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.agent.thread_folder.layout import (
    OUTPUTS,
    PREVIEWS,
    SOURCES,
    remove_entry,
)
from modules.chat.models import ChatThread
from shared.config import get_storage_settings

_guard = threading.Lock()
_done: set[Path] = set()


def retire_once(session: Session, workspace_id: int) -> None:
    """Remove `agent/sources/`, `agent/outputs/previews/` and folders of threads that are gone.

    Commits the session's read before touching the disk.
    """
    storage = get_storage_settings()
    agent = storage.agent_working_dir(workspace_id)
    with _guard:
        if agent in _done:
            return
        _done.add(agent)
    live = {
        str(thread_id)
        for thread_id in session.scalars(
            select(ChatThread.id).where(
                ChatThread.workspace_id == workspace_id,
                ChatThread.opencode_session_id.is_not(None),
            )
        )
    }
    session.commit()
    shutil.rmtree(agent / SOURCES, ignore_errors=True)
    shutil.rmtree(agent / OUTPUTS / PREVIEWS, ignore_errors=True)
    threads = storage.agent_threads_dir(workspace_id)
    if threads.is_dir():
        for folder in threads.iterdir():
            if folder.name not in live:
                remove_entry(folder)
