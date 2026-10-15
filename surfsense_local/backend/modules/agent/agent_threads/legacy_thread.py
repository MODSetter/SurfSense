"""Telling a thread made before each thread had its own folder.

An opencode session cannot move, and the folder every thread once shared
holds every thread's folder, so such a thread could read them all: it may be
read back, never continued.
"""

import os
from pathlib import Path

from modules.agent.opencode_client import OpencodeClient

LEGACY_TURN = (
    "This agent chat was started before each chat kept its own sources. "
    "Start a new chat to continue."
)

# A legacy session stays legacy, so that answer holds for the run. One in its own
# folder is asked about each turn: opencode can lose it later, and answers 404.
_legacy: set[str] = set()


async def is_legacy(client: OpencodeClient, session_id: str, folder: Path) -> bool:
    """Whether the session works anywhere but the thread's own folder."""
    if session_id in _legacy:
        return True
    directory = await client.session_directory(session_id)
    if _normal(directory) == _normal(folder):
        return False
    _legacy.add(session_id)
    return True


def forget_legacy(session_id: str) -> None:
    """Drop a deleted session's answer."""
    _legacy.discard(session_id)


def _normal(path: str | Path) -> str:
    return os.path.normcase(os.path.realpath(path))
