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

# A session's folder never changes, so it is asked once per run.
_legacy: dict[str, bool] = {}


async def is_legacy(client: OpencodeClient, session_id: str, folder: Path) -> bool:
    """Whether the session works anywhere but the thread's own folder."""
    if session_id not in _legacy:
        directory = await client.session_directory(session_id)
        _legacy[session_id] = _normal(directory) != _normal(folder)
    return _legacy[session_id]


def forget_legacy(session_id: str) -> None:
    """Drop a deleted session's answer."""
    _legacy.pop(session_id, None)


def _normal(path: str | Path) -> str:
    return os.path.normcase(os.path.realpath(path))
